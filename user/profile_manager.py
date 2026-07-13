import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from supabase import AuthApiError
from utils.supabase_client import supabase as _shared_supabase
from utils.logger_handler import logger

# 1. 定义用户画像的数据结构 (V2: 活的画像，对话中自然积累)
class UserProfile(BaseModel):
    """留学生画像模型 — V2 修士向"""
    # ── 基础背景（表单优先）──
    target_degree: str = Field(default="修士", description="修士 / 学部")
    jlpt_level: str = Field(default="无", description="日语等级 (N1-N5)")
    english_score: str = Field(default="未参加", description="托福/托业/雅思成绩")
    gpa_score: float = Field(default=0.0, ge=0.0, description="绩点数值")
    gpa_scale: float = Field(default=4.0, ge=1.0, description="满绩点 (4.0/4.3/5.0/100)")
    undergraduate_school: str = Field(default="未设定", description="本科院校背景")
    target_major: str = Field(default="未设定", description="目标专业")
    research_area: str = Field(default="", description="研究方向，如 NLP/地震工学")
    # 学部专用（修士可忽略）
    eju_score: int = Field(default=0, ge=0, le=800, description="EJU总分（学部用）")

    # ── AI 自由存储（无 schema，AI 觉得该记就记）──
    facts: Dict[str, Any] = Field(default_factory=dict, description="AI自由存储：实习/项目/论文/获奖等")

    # ── 时间线 ──
    events: List[Dict[str, str]] = Field(default_factory=list,
        description="[{'date':'2026-07','event':'N1合格','source':'chat'}]")

    # ── 申请追踪（V2.2: 每校独立 track，每教授独立追踪）──
    # applications: [{school, stage, needs_contact, contact_status, contact_date,
    #   professors: [{name, status, date}], deadlines: {name: date}, notes}]
    applications: List[Dict[str, Any]] = Field(default_factory=list,
        description="每所志愿校独立追踪，professors 内每个教授有 status+date")
    # backward compat
    target_professors: List[str] = Field(default_factory=list)
    application_stage: str = Field(default="")

    # ── 元数据：每条字段的来源和更新时间 ──
    field_sources: Dict[str, Dict[str, str]] = Field(default_factory=dict,
        description="{'jlpt_level':{'source':'form','at':'2026-07-01'}}")

    # ── 报告持久化（V1 兼容）──
    report_status: Optional[str] = Field(default="NONE", description="报告状态 (NONE, DRAFT, REFINED)")
    suggestions: Optional[str] = Field(default=None, description="报告的核心建议")
    report_content: Dict[str, Any] = Field(default_factory=dict, description="报告完整结构化内容")
    report_last_updated: Optional[str] = Field(default=None, description="报告更新时间")

    # ── 向后兼容：V1 代码仍可读 gpa ──
    @property
    def gpa(self) -> float:
        """归一化 GPA 到 4.0 scale，兼容 V1 代码"""
        if self.gpa_scale and self.gpa_scale > 0 and self.gpa_score > 0:
            return round(self.gpa_score / self.gpa_scale * 4.0, 2)
        return self.gpa_score

    def to_dict(self):
        d = self.model_dump()
        d["gpa"] = self.gpa  # 兼容 V1 读取
        return d

    def set_field(self, field: str, value: Any, source: str = "chat_inferred"):
        """设置字段并记录来源和时间"""
        setattr(self, field, value)
        self.field_sources[field] = {"source": source, "at": datetime.now().isoformat()}

    def add_fact(self, key: str, value: Any):
        """AI 自由添加 fact"""
        self.facts[key] = value
        self.field_sources[f"facts.{key}"] = {"source": "chat_inferred", "at": datetime.now().isoformat()}

    def add_event(self, date: str, event: str, source: str = "chat"):
        """添加时间线事件，按日期去重"""
        if not any(e["event"] == event for e in self.events):
            self.events.append({"date": date, "event": event, "source": source})
            self.events.sort(key=lambda e: e["date"])

    def upsert_application(self, school: str, major: str = "", **kwargs):
        """添加或更新一所志愿校的追踪记录。school+major 联合去重。"""
        key = f"{school}|{major}" if major else school
        for app in self.applications:
            app_key = f"{app['school']}|{app.get('major', '')}" if app.get('major') else app['school']
            if app_key == key:
                app.update(kwargs)
                return app
        app = {"school": school, "major": major,
               "stage": "preparing", "needs_contact": False,
               "professors": [], "deadlines": {}, "notes": ""}
        app.update(kwargs)
        self.applications.append(app)
        return app

    def add_professor_attempt(self, school: str, professor: str, status: str = "pending", date: str = ""):
        """记录一位教授的套磁尝试。如已有则更新状态。"""
        app = self.upsert_application(school, "", needs_contact=True, stage="contacting")
        for p in app.setdefault("professors", []):
            if p["name"] == professor:
                p["status"] = status
                if date:
                    p["date"] = date
                return app
        app["professors"].append({"name": professor, "status": status, "date": date or datetime.now().strftime("%Y-%m-%d")})
        return app

# ── Profile extraction prompt（V2.2: 每轮对话后 LLM 扫描新增信息，支持多校申请追踪）──
PROFILE_EXTRACTION_PROMPT = """你是信息提取助手。分析对话，提取学生的新信息，只输出变化的字段。

学生当前画像：
{current_profile}

最近对话：
{conversation}

输出 JSON，只包含有变化的字段（没变化就不输出）。字段说明：

基础字段：
- jlpt_level: N1/N2/N3/N4/N5/无
- english_score: 如 "TOEFL 95" / "TOEIC 800" / "IELTS 7.0"
- target_major: 目标专业
- research_area: 研究方向
- undergraduate_school: 本科院校
- gpa_score: 绩点数值
- gpa_scale: 满绩点（4.0/4.3/5.0/100）
- eju_score: 仅当学生明确是学部申请者时才提取
- facts: 自由对象，如 {"实习":"腾讯NLP 3个月"}。key用中文描述，不要覆盖已有key
- events: 数组，如 [{"date":"2026-07","event":"N1合格","source":"chat"}]

申请追踪（V2.2 多校独立追踪）：
- applications: 数组，每项代表一所志愿校的完整追踪记录。格式：
  [
    {{
      "school": "京都大学 情报理工",
      "stage": "contacting",           // preparing/contacting/applying/exam/waiting/decided
      "needs_contact": true,           // 是否需要套磁
      "professors": [                  // 该校联系的教授列表
        {{"name": "田中太郎", "status": "sent", "date": "2026-07-01"}}
      ],
      "deadlines": {{"出愿": "2026-12-15"}},  // 截止日期
      "notes": "田中2周未回，考虑换人"         // 备注
    }}
  ]
  professor status 取值: pending(准备联系) / sent(已发信) / replied(收到回复) / rejected(婉拒) / no_reply(无回复超2周) / interview(获得面试)

  重要规则：
  - 只输出学生明确提到的新学校或状态变更，不要编造
  - 如果学生说"给某某教授发了邮件"，新增该校 application 并添加 professor(status=sent)，同时更新 stage 为 contacting
  - 如果学生说"某某教授回了"，更新对应 professor 的 status=replied
  - 如果学生说"某某教授两周没回"，更新 status=no_reply
  - 阶段变更检测（根据学生陈述更新 stage）：
    * 学生说"开始准备材料""在看出愿""准备出願"等 → stage=applying
    * 学生说"要去考试""参加笔试""面试通知""准考证"等 → stage=exam
    * 学生说"等结果""合否""合格発表""等通知"等 → stage=waiting
    * 学生说"录取了""合格了""确定去""内定"等 → stage=decided
    * 学生说"出願截止是X月X日"等 → 添加到该校 deadlines
  - 每所学校在 applications 中只出现一次（用 school 字段去重），状态变更时更新已有记录
  - 不要删除已有的 applications，只更新或新增

- target_professors: 数组，如 ["东大 田中太郎"]（向后兼容，简单列表）
- application_stage: 字符串（向后兼容，单校模式的总阶段）

规则：
1. 学生明确说的 > 你推断的。不确定就别写。
2. facts 和 events 只追加新条目，不覆盖已有。
3. 如果有新的申请信息（套磁、出愿、考试等），优先用 applications 格式输出。
4. 如果没有任何新信息，返回 {{}}。

JSON:"""

# 2. 线上版管理器 (Supabase)
class ProfileManager:
    def __init__(self):
        self.supabase = _shared_supabase

    def get_profile(self, user_id: str) -> UserProfile:
        """从 Supabase 获取画像，若无则返回默认对象"""
        if not self.supabase:
            return UserProfile()

        try:
            response = self.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
            if response.data and len(response.data) > 0:
                data = response.data[0]
                filtered_data = {k: v for k, v in data.items() if k in UserProfile.model_fields}
                return UserProfile(**filtered_data)
        except Exception as e:
            logger.error(f"读取数据库失败: {e}")

        return UserProfile()

    def save_profile(self, user_id: str, profile: UserProfile):
        """保存 UserProfile 对象到数据库"""
        if not self.supabase:
            logger.warning("无法保存：数据库未连接")
            return

        data = profile.to_dict()
        data["id"] = user_id

        try:
            self.supabase.table("user_profiles").upsert(data).execute()
            logger.info(f"用户 {user_id} 画像已同步至数据库")
        except Exception as e:
            logger.error(f"保存数据库失败: {e}")
            raise  # re-raise so caller sees the error

    def merge_delta(self, profile: UserProfile, delta: dict) -> UserProfile:
        """合并 LLM 提取的增量信息。form 来源的字段不会被 chat_inferred 覆盖。"""
        for field, value in delta.items():
            if field in ("facts", "events", "target_professors", "applications"):
                continue  # 下面单独处理
            if field not in UserProfile.model_fields:
                continue
            # form > chat_inferred
            existing_source = profile.field_sources.get(field, {}).get("source")
            if existing_source == "form":
                continue
            profile.set_field(field, value, "chat_inferred")

        # facts: 追加不覆盖
        for k, v in delta.get("facts", {}).items():
            if k not in profile.facts:
                profile.add_fact(k, v)

        # events: 追加去重
        for e in delta.get("events", []):
            profile.add_event(e.get("date", ""), e.get("event", ""), e.get("source", "chat"))

        # professors: 追加去重
        for prof in delta.get("target_professors", []):
            if prof not in profile.target_professors:
                profile.target_professors.append(prof)

        # applications: 按 school 去重合并，逐校 upsert
        for app_delta in delta.get("applications", []):
            school = app_delta.get("school", "")
            if not school:
                continue
            existing = profile.upsert_application(school)
            # merge top-level fields
            for k in ("stage", "needs_contact", "notes"):
                if k in app_delta and app_delta[k]:
                    existing[k] = app_delta[k]
            # merge professors: dedupe by name, update status if newer
            for prof in app_delta.get("professors", []):
                profile.add_professor_attempt(
                    school, prof.get("name", ""),
                    prof.get("status", "pending"),
                    prof.get("date", "")
                )
            # merge deadlines
            for k, v in app_delta.get("deadlines", {}).items():
                existing.setdefault("deadlines", {})[k] = v

        return profile

    def extract_facts_from_chat(
        self, profile: UserProfile, conversation: str, chat_model=None
    ) -> dict:
        """LLM 扫描对话，返回增量的 dict（只有变化的字段）。chat_model 需传入。"""
        if not chat_model:
            return {}
        try:
            current_json = json.dumps({
                "jlpt_level": profile.jlpt_level,
                "english_score": profile.english_score,
                "target_major": profile.target_major,
                "research_area": profile.research_area,
                "undergraduate_school": profile.undergraduate_school,
                "gpa_score": profile.gpa_score,
                "gpa_scale": profile.gpa_scale,
                "target_professors": profile.target_professors,
                "application_stage": profile.application_stage,
                "applications": profile.applications,
                "facts": profile.facts,
                "events": profile.events[-5:] if profile.events else [],
            }, ensure_ascii=False)
            prompt = PROFILE_EXTRACTION_PROMPT.format(
                current_profile=current_json, conversation=conversation)
            resp = chat_model.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            # Strip markdown fences if present
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            logger.warning(f"Profile extraction skipped: {e}")
            return {}

    def format_for_prompt(self, profile: UserProfile) -> str:
        """将画像格式化为 Agent 容易理解的字符串 (V2 修士向)"""
        parts = ["【学生背景画像】"]
        parts.append(f"- 学位阶段: {profile.target_degree}")
        parts.append(f"- 日语能力: {profile.jlpt_level}")
        if profile.eju_score and profile.eju_score > 0:
            parts.append(f"- EJU总分: {profile.eju_score}")
        if profile.gpa_score > 0:
            parts.append(f"- GPA: {profile.gpa_score}/{profile.gpa_scale}")
        parts.append(f"- 英语成绩: {profile.english_score or '未提供'}")
        parts.append(f"- 目标专业: {profile.target_major or '未设定'}")
        parts.append(f"- 研究方向: {profile.research_area or '未设定'}")
        parts.append(f"- 本科院校: {profile.undergraduate_school or '未设定'}")

        if profile.facts:
            facts_str = "\n".join(f"  - {k}: {v}" for k, v in profile.facts.items())
            parts.append(f"\n【经历与项目】\n{facts_str}")

        if profile.applications:
            app_lines = []
            for app in profile.applications:
                stage_label = {"preparing": "准备", "contacting": "套磁", "applying": "出愿",
                    "exam": "考试", "waiting": "等结果", "decided": "确定"}.get(app.get("stage", ""), app.get("stage", ""))
                line = f"  [{stage_label}] {app['school']}"
                profs = app.get("professors", [])
                if profs:
                    prof_strs = [f"{p['name']}({p.get('status','?')})" for p in profs]
                    line += f" | 教授: {', '.join(prof_strs)}"
                deadlines = app.get("deadlines", {})
                if deadlines:
                    line += f" | 截止: {'; '.join(f'{k}:{v}' for k,v in deadlines.items())}"
                if app.get("notes"):
                    line += f" | {app['notes']}"
                app_lines.append(line)
            parts.append("\n【申请追踪】\n" + "\n".join(app_lines))

        if profile.target_professors:
            profs = ", ".join(profile.target_professors)
            parts.append(f"\n- 意向教授: {profs}")

        if profile.events:
            events_str = "\n".join(f"  {e['date']} | {e['event']}" for e in profile.events[-10:])
            parts.append(f"\n【重要时间线】\n{events_str}")

        if profile.application_stage:
            parts.append(f"\n- 当前申请阶段: {profile.application_stage}")

        if profile.report_status != "NONE" and profile.suggestions:
            parts.append(f"\n【历史规划报告】(状态:{profile.report_status})")
            parts.append(profile.suggestions)

        return "\n".join(parts)

    def send_reset_password_email(self, email: str):
        """发送重置密码验证码 (OTP)"""
        if not self.supabase: return
        try:
            return self.supabase.auth.reset_password_for_email(email)
        except AuthApiError as e:
            logger.warning(f"邮件发送失败: {e}")
            if "rate limit" in str(e).lower():
                raise Exception("邮件发送过于频繁，请稍后再试")
            else:
                raise e

    def verify_reset_otp(self, email: str, token: str):
        """验证 6 位验证码"""
        if not self.supabase: return None
        try:
            res = self.supabase.auth.verify_otp({
                "email": email,
                "token": token,
                "type": "recovery"
            })
            return res
        except Exception as e:
            logger.error(f"验证码校验失败: {e}")
            raise e

    def update_password(self, new_password: str):
        """更新密码 (需在 verify_reset_otp 成功后的会话中调用)"""
        if not self.supabase: return
        try:
            return self.supabase.auth.update_user({"password": new_password})
        except Exception as e:
            logger.error(f"更新密码失败: {e}")
            raise e

profile_mgr = ProfileManager() # 创建全局唯一的实例
# 3. 测试逻辑
if __name__ == "__main__":
    test_id = "00000000-0000-0000-0000-000000000001"
    print(f"--- 运行测试: {test_id} ---")
    loaded = profile_mgr.get_profile(test_id)
    print(profile_mgr.format_for_prompt(loaded))