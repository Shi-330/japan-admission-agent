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
        """Intent classification — pure LLM, no keyword matching.
        Returns: chat / match / report / qa / search_schools"""
        if not chat_model:
            return "chat"
        try:
            resp = chat_model.invoke(
                f"""判断意图，只输出一个词（chat/qa/search_schools/match/report）：

用户说："{prompt}"

意图规则：
- search_schools：明确在找/筛选学校（有具体条件如"不要英语""东京""NLP方向""免笔试"等）
- match：明确说"匹配""帮我选校""根据我的背景推荐"等
- qa：问具体申请知识（流程/材料/考试/语言要求等）
- chat：闲聊、陈述、进度更新（如"我想考大学院""在准备出愿""给教授发了邮件"等）
- report：要生成规划报告

只输出一个词：""")
            text = resp.content.lower() if hasattr(resp, "content") else str(resp).lower()
            for i in ["search_schools", "match", "report", "qa"]:
                if i in text:
                    return i
            return "chat"
        except Exception:
            return "chat"
