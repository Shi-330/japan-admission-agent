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
        """Quick LLM intent classification. Returns: chat / match / report / qa."""
        if not chat_model:
            return "qa"
        intent_prompt = f"""判断意图，只输出一个词：
用户说："{prompt}"
背景：{profile_str}
输出: chat / match / report / qa"""
        try:
            resp = chat_model.invoke(intent_prompt)
            for i in ["chat", "match", "report", "qa"]:
                if i in resp.content.lower():
                    return i
        except Exception:
            pass
        return "qa"
