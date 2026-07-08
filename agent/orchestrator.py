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
        """Intent classification. LLM-based with keyword fast-path for obvious cases.
        Returns: chat / match / report / qa / search_schools"""
        p = prompt.lower()

        # Obvious fast-path (no LLM needed) — only trigger match for explicit matching requests
        if any(k in p for k in ["匹配我的背景", "适合我", "定校"]):
            return "match"
        if any(k in p for k in ["报告", "计划书", "研究计划"]):
            return "report"

        # Everything else: LLM decides
        if not chat_model:
            return "chat"
        try:
            resp = chat_model.invoke(
                f"""判断意图，只输出一个词：
用户说："{prompt}"
search_schools=搜索/筛选学校（如"有没有不要英语的""东京的学校""NLP方向"等）
match=根据我的背景分數匹配（仅当明确说"匹配"时）
report=生成规划报告
qa=申请流程/材料/考试等知识问答
chat=闲聊/进度更新/套磁/教授
输出: chat / match / report / qa / search_schools""")
            text = resp.content.lower() if hasattr(resp, "content") else str(resp).lower()
            for i in ["search_schools", "match", "report", "qa"]:
                if i in text:
                    return i
            return "chat"
        except Exception:
            return "chat"
