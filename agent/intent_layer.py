"""
Intent Layer Engine — unified intent + flow + action classification.
Single LLM call replaces classify_intent() + flow_router.route() + keyword detection.

Stateless, Streamlit-free — follows the agent/ module convention.
"""
import json
from typing import Optional


# ── Lightweight greetings (no LLM needed) ──
LIGHT_GREETINGS = frozenset([
    "你好", "嗨", "hi", "hello", "hey", "在吗", "在不在", "哈喽", "早",
    "晚上好", "早上好", "下午好",
])


def is_light_greeting(query: str) -> bool:
    """Check if query is a casual greeting that needs no LLM."""
    q = query.strip().lower()
    return q in LIGHT_GREETINGS or len(q) <= 2


# Keywords that signal the query likely has application intent
_SHORT_QUERY_SIGNALS = frozenset([
    "大学", "学校", "教授", "出願", "出愿", "考试", "考試", "申请", "申請",
    "推荐", "推薦", "匹配", "选校", "選校", "套磁", "面接", "面试", "面試",
    "N1", "N2", "N3", "N4", "N5", "TOEFL", "TOEIC", "IELTS",
    "情报", "情報", "理工", "研究科", "研究室", "研究生", "修士", "博士", "日语", "日語",
    "専攻", "专攻", "方向", "コース", "進学", "进学",
    "英语", "英語", "东京", "京都", "大阪", "早稻田", "计划书", "报告",
])


def is_short_query(query: str) -> bool:
    """
    Short query without application-signaling keywords can skip full LLM classification.
    Returns True for simple questions that should go straight to 'chat'.
    """
    q = query.strip()
    if len(q) > 10:
        return False
    return not any(k in q for k in _SHORT_QUERY_SIGNALS)


# ── Unified classification prompt ──
CLASSIFY_PROMPT = """你是一个日本升学顾问系统的意图分析引擎。分析当前用户问题并结合最近对话，输出结构化JSON。不要markdown代码块，不要解释。

## 当前用户问题
{query}

## 最近对话（最近5轮）
{history}

## 学生画像
{profile}

## 申请进度
{stage_ctx}

## 可选筛选标签（nav_plaza的filter只能从这里选，不能编造）
{valid_tags}

## 可追踪学校（track_school的name只能从这里选，不能编造）
{school_names}

## 输出格式（严格JSON，不要```json```代码块）
{{"intent":"chat|qa|search_schools|match|report","flow":"school_search|professor_contact|application|exam_prep|general","depth":0|1|2,"prompt":"根据flow+depth的简短引导语（≤50字）","actions":[{{"type":"nav_plaza","filter":"标签1 标签2","prompt":"去广场筛选一下？"}},{{"type":"track_school","name":"学校完整名称"}},{{"type":"remind_prof","school":"学校名","professor":"教授名","days_since_contact":天数}},{{"type":"suggest_report"}}]}}

## 规则
### intent
- search_schools：明确在找/筛选学校。**"我想考XX"或"考XX"（XX=专业名，如"考法学""考计算机""我想考环境学"）都属于search_schools。** 其他例："东京的XX方向""不要英语的学校""XX研究室"
- match：明确说"匹配""帮我选校""根据背景推荐"
- qa：问具体申请知识（流程/材料/考试/语言要求等）
- report：明确要生成规划报告
- chat：闲聊、陈述、进度更新、话题转换

### flow
- school_search：在找学校、筛选、对比院校
- professor_contact：在聊套磁、教授、发邮件、联系
- application：在聊出愿、材料、截止日
- exam_prep：在聊考试、备考、笔试、面试
- general：闲聊、知识问答、其他

### depth
- 0：刚开始聊这个主题，没有具体信息
- 1：有了具体方向/学校/条件，正在深入
- 2：条件已明确，可以执行动作（弹卡片/提醒/确认）

### prompt（根据flow+depth生成引导语）
- school_search depth0：引导学生说出专业方向、语言要求、地域偏好
- school_search depth1：帮学生缩小范围，条件够时建议去广场
- school_search depth2：建议学生去广场筛选
- professor_contact depth0：问目标学校和教授
- professor_contact depth1：帮学生写邮件、跟进时间线
- professor_contact depth2：提醒超2周未回复建议跟进或换教授
- application depth0：问哪所学校、什么专业
- application depth1：帮学生梳理材料清单和截止日
- application depth2：提醒确认截止日期、检查材料
- exam_prep depth0：问目标学校和考试类型
- exam_prep depth1：给复习建议和过去问方向
- exam_prep depth2：可模拟面试或提醒考试日期
- general：正常回复即可

### actions（可选，没有条件则输出空数组[]）
- nav_plaza：条件=用户表达了学校筛选条件。filter只从{valid_tags}选，prompt自由写（如"去广场筛选一下？"）
- track_school：条件=学生提到任何学校名称（即使只说简称如"京大""东大"也要尝试匹配）。name尽量匹配{school_names}中的完整名称，如果只记得简称也可以写简称（系统会自动匹配）
- remind_prof：条件=用户提到某教授超期未回复
- suggest_report：条件=用户在做整体规划或问下一步

JSON:"""


# ── Safe defaults ──
DEFAULT_RESULT = {
    "intent": "chat",
    "flow": "general",
    "depth": 0,
    "prompt": "",
    "actions": [],
}


class IntentLayerEngine:
    """
    Unified intent, flow, depth, and action classifier.
    Makes ONE LLM call to replace the old classify_intent() + flow_router.route()
    + keyword-based action detection.
    """

    def __init__(self, catalog: list[dict] = None):
        """
        Args:
            catalog: SCHOOL_CATALOG list. Injected for testability;
                     defaults to an empty list if not provided.
        """
        self.catalog = catalog or []
        self.valid_tags: frozenset[str] = self._collect_tags()
        self.valid_school_names: frozenset[str] = frozenset(
            s["name"] for s in self.catalog
        )
        self._tags_str = "、".join(sorted(self.valid_tags)) if self.valid_tags else "（无）"
        self._names_str = "、".join(sorted(self.valid_school_names)) if self.valid_school_names else "（无）"

    # ── Public API ──

    def classify(
        self,
        query: str,
        history: list[dict],
        profile_str: str,
        stage_ctx: str,
        chat_model=None,
    ) -> dict:
        """
        Single LLM call → {intent, flow, depth, prompt, actions}.
        Falls back to safe defaults on any error.
        """
        if not chat_model:
            return dict(DEFAULT_RESULT)

        history_text = self._format_history(history)
        prompt = CLASSIFY_PROMPT.format(
            query=query,
            history=history_text,
            profile=profile_str,
            stage_ctx=stage_ctx,
            valid_tags=self._tags_str,
            school_names=self._names_str,
        )

        try:
            resp = chat_model.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            result = self._parse_json(text)
        except Exception:
            return dict(DEFAULT_RESULT)

        # Ensure all expected keys exist
        out = dict(DEFAULT_RESULT)
        out["intent"] = result.get("intent", "chat")
        out["flow"] = result.get("flow", "general")
        out["depth"] = result.get("depth", 0)
        out["prompt"] = result.get("prompt", "")
        out["actions"] = self.validate_actions(result.get("actions", []))
        return out

    def validate_actions(self, actions: list[dict]) -> list[dict]:
        """
        Filter actions against known-good whitelists.
        Drops hallucinated filter tokens and non-existent school names.
        """
        if not actions:
            return []

        valid = []
        for action in actions:
            atype = action.get("type", "")
            if atype == "nav_plaza":
                cleaned = self._clean_nav_plaza(action)
                if cleaned:
                    valid.append(cleaned)
            elif atype == "track_school":
                resolved = self._resolve_school_name(action.get("name", ""))
                if resolved:
                    action["name"] = resolved  # normalize to full catalog name
                    valid.append(action)
            elif atype == "remind_prof":
                if action.get("school") and action.get("professor"):
                    valid.append(action)
            elif atype == "suggest_report":
                valid.append(action)
            # Unknown types are silently dropped
        return valid

    def actions_to_sse_events(self, actions: list[dict]) -> dict:
        """
        Convert validated actions to frontend-compatible SSE event fields.
        Returns a dict to merge into the 'done' SSE event:

            {"nav_suggestion": {...}}      — from nav_plaza
            {"suggested_schools": [...]}   — from track_school
            {"reminders": [...]}           — from remind_prof
            {"report_suggestion": true}    — from suggest_report
            {}                              — no actionable items
        """
        result = {}
        nav = None
        schools = []
        reminders = []

        for action in actions:
            atype = action.get("type", "")
            if atype == "nav_plaza" and nav is None:
                nav = {
                    "action": "filter_plaza",
                    "filter": action.get("filter", ""),
                    "prompt": action.get("prompt", "去广场筛选一下？"),
                }
            elif atype == "track_school":
                schools.append(action["name"])
            elif atype == "remind_prof":
                reminders.append({
                    "school": action.get("school", ""),
                    "professor": action.get("professor", ""),
                    "days_since_contact": action.get("days_since_contact", 14),
                })
            elif atype == "suggest_report":
                result["report_suggestion"] = True
            elif atype == "school_cards":
                result["school_cards"] = action.get("cards", [])
            elif atype == "discovered_schools":
                result["discovered_schools"] = action.get("schools", [])

        if nav:
            result["nav_suggestion"] = nav
        if schools:
            result["suggested_schools"] = schools
        if reminders:
            result["reminders"] = reminders

        return result

    # ── Internal helpers ──

    def _clean_nav_plaza(self, action: dict) -> Optional[dict]:
        """Drop hallucinated filter tokens; keep only tokens from valid_tags."""
        tokens = action.get("filter", "").split()
        valid_tokens = [t for t in tokens if t in self.valid_tags]
        if not valid_tokens:
            return None
        return {
            "type": "nav_plaza",
            "filter": " ".join(valid_tokens),
            "prompt": action.get("prompt", "去广场筛选一下？"),
        }

    def _resolve_school_name(self, name: str) -> Optional[str]:
        """Match a partial school name to the full catalog name.
        E.g., '京都大学' → '京都大学 情报学研究科'.
        Returns None if no match found."""
        if name in self.valid_school_names:
            return name
        # Try prefix match (LLM often outputs just the university name)
        for full in self.valid_school_names:
            short = full.split()[0] if ' ' in full else full
            if name == short or name in full:
                return full
        return None

    def _collect_tags(self) -> frozenset[str]:
        """Union of all 'tags' arrays across the catalog."""
        tags = set()
        for s in self.catalog:
            for t in s.get("tags", []):
                tags.add(t)
        return frozenset(tags)

    @staticmethod
    def _format_history(history: list[dict], max_messages: int = 5) -> str:
        """Convert [{role, content}] to a readable conversation string."""
        if not history:
            return "（新对话）"
        lines = []
        for m in history[-max_messages:]:
            role = m.get("role", "unknown")
            content = m.get("content", "")[:200]
            label = "学生" if role == "user" else "助手"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from LLM response (handles markdown fences)."""
        t = text.strip()
        if "```" in t:
            parts = t.split("```")
            # Take the second code block (index 1), skip optional "json" prefix
            t = parts[1]
            if t.startswith("json"):
                t = t[4:]
        return json.loads(t.strip())
