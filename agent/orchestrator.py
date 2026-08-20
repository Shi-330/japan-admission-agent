"""
Chat orchestrator — business logic shared by Streamlit and FastAPI.
No UI dependency. Handles chat → extraction → profile merge pipeline.
"""
from user.profile_manager import ProfileManager, UserProfile
from utils.logger_handler import logger


# ── 事实信号检测(纯规则,零 LLM) ──
# 只在学生暴露了个人信息(成绩/背景/方向/经历)时才值得跑一次事实抽取。
_SCORE_TOKENS = frozenset([
    "N1", "N2", "N3", "N4", "N5", "JLPT", "TOEFL", "TOEIC", "IELTS",
    "托福", "托业", "雅思", "GPA", "绩点", "均分", "EJU",
])

_FIRST_PERSON = frozenset([
    "我是", "我在", "我读", "我学", "我本科", "我毕业", "我的", "我研究",
    "我做过", "我实习", "我工作", "我打算", "我计划", "我来自", "我准备",
])


def has_fact_signal(message: str) -> bool:
    """判断消息是否可能包含学生个人信息(成绩/学校/方向/经历)。

    纯关键词规则,不调 LLM。无信号的消息(如「谢谢」「好的」)跳过事实抽取。
    """
    if not message:
        return False
    m = message.strip()
    up = m.upper()
    if any(t in up for t in _SCORE_TOKENS):
        return True
    return any(p in m for p in _FIRST_PERSON)


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
        if not has_fact_signal(user_message):
            return profile  # 无事实信号,跳过 LLM 抽取(省一次调用)
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
