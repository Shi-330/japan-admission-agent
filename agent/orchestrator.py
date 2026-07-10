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
        history: list[dict] = None,
    ) -> UserProfile:
        """
        After each chat turn: extract new facts → merge → save.
        Includes conversation history (last 3 turns) for multi-turn context.
        Returns updated profile. Best-effort — never raises.
        """
        try:
            # Build conversation with history for multi-turn context
            from agent.intent_layer import IntentLayerEngine
            parts = [IntentLayerEngine._format_history(history, max_messages=6)] if history else []
            # Append current turn
            parts.append(f"学生: {user_message}")
            parts.append(f"助手: {assistant_response}")
            conversation = "\n".join(p for p in parts if p)

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
