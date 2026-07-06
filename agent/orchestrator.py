"""
Chat orchestrator — business logic shared by Streamlit and FastAPI.
No UI dependency. Handles chat → extraction → profile merge pipeline.
"""
from user.profile_manager import ProfileManager, UserProfile
from utils.logger_handler import logger


class ChatOrchestrator:
    """Lightweight chat pipeline shared across frontends."""

    def __init__(self, profile_mgr: ProfileManager = None):
        self.profile_mgr = profile_mgr or ProfileManager()

    def finish_turn(
        self,
        user_id: str,
        profile: UserProfile,
        user_message: str,
        assistant_response: str,
        chat_model=None,
    ) -> UserProfile:
        """
        After each chat turn: extract new facts → merge → save.
        Returns updated profile. Best-effort — never raises.
        """
        try:
            conversation = f"用户: {user_message}\n助手: {assistant_response}"
            delta = self.profile_mgr.extract_facts_from_chat(
                profile, conversation, chat_model
            )
            if delta and delta != {}:
                profile = self.profile_mgr.merge_delta(profile, delta)
                self.profile_mgr.save_profile(user_id, profile)
                logger.info(f"Profile updated from chat: {list(delta.keys())}")
        except Exception as e:
            logger.debug(f"Profile extraction skipped: {e}")
        return profile

    def classify_intent(self, prompt: str, profile_str: str, chat_model=None) -> str:
        """Fast intent classification. Returns: chat / match / report / qa.
        Uses keyword match first (no LLM call), falls back to LLM for ambiguous cases."""
        p = prompt.lower()

        # Fast keyword match — catch 90% of cases without LLM
        match_keywords = ["匹配", "选校", "推荐学校", "哪些学校", "适合我", "定校", "学校推荐"]
        report_keywords = ["报告", "规划", "计划书", "研究计划", "出愿计划"]
        qa_keywords = ["怎么", "如何", "什么", "为什么", "能不能", "需要什么", "条件",
                       "要求", "流程", "材料", "截止", "考试内容", "面试", "分数", "gpa",
                       "n1", "n2", "jlpt", "toefl", "toeic", "ielts", "英语", "日语",
                       "出愿", "套磁", "研究计划", "内诺", "在留", "签证", "入试",
                       "申请", "修士", "研究生", "教授", "学费", "奖学金"]

        if any(k in p for k in match_keywords):
            return "match"
        if any(k in p for k in report_keywords):
            return "report"
        if any(k in p for k in qa_keywords):
            return "qa"

        # Only LLM classify if keyword match unclear
        if not chat_model:
            return "chat"
        intent_prompt = f"""判断意图，只输出一个词：
用户说："{prompt}"
意图说明：match=选校匹配 report=规划报告 qa=知识问答 chat=闲聊/申请进度
输出: chat / match / report / qa"""
        try:
            resp = chat_model.invoke(intent_prompt)
            for i in ["chat", "match", "report", "qa"]:
                if i in resp.content.lower():
                    return i
        except Exception:
            pass
        return "chat"
