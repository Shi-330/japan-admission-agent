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

    # ── 申请追踪（V2.2 状态机接管）──
    target_professors: List[str] = Field(default_factory=list,
        description="目标教授列表: ['东大 田中', '早大 佐藤']")
    application_stage: str = Field(default="", description="preparing/contacting/applying/waiting/done")

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

# ── Profile extraction prompt（V2.1: 每轮对话后 LLM 扫描新增信息）──
PROFILE_EXTRACTION_PROMPT = """你是信息提取助手。分析对话，提取学生的新信息，只输出变化的字段。

学生当前画像：
{current_profile}

最近对话：
{conversation}

输出 JSON，只包含有变化的字段（没变化就不输出）。字段说明：
- jlpt_level: N1/N2/N3/N4/N5/无
- english_score: 如 "TOEFL 95" / "TOEIC 800" / "IELTS 7.0"
- target_major: 目标专业
- research_area: 研究方向
- undergraduate_school: 本科院校
- gpa_score: 绩点数值
- gpa_scale: 满绩点（4.0/4.3/5.0/100）
- target_professors: 数组，如 ["东大 田中太郎", "早大 佐藤花子"]
- application_stage: preparing/contacting/applying/waiting/done
- facts: 自由对象，如 {"实习":"腾讯NLP 3个月"}。key用中文描述，不要覆盖已有key
- events: 数组，如 [{"date":"2026-07","event":"N1合格","source":"chat"}]
- eju_score: 仅当学生明确是学部申请者时才提取

规则：
1. 学生明确说的 > 你推断的。不确定就别写。
2. facts 和 events 只追加新条目，不覆盖已有。
3. 如果没有任何新信息，返回 {{}}。

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

    def merge_delta(self, profile: UserProfile, delta: dict) -> UserProfile:
        """合并 LLM 提取的增量信息。form 来源的字段不会被 chat_inferred 覆盖。"""
        for field, value in delta.items():
            if field in ("facts", "events", "target_professors"):
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