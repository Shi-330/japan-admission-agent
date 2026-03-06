import hashlib
from typing import Dict, Any, Optional, Generator
from pydantic import BaseModel
from agent.react_agent import ReactAgent
from user.profile_manager import UserProfile

class HeadlessAgent:
    """
    A decoupled Agent class designed for the modern architecture.
    This core component is independent of any UI framework (Streamlit/React).
    """

    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile
        # Initialize the underlying ReactAgent with the profile dictionary
        self.agent_core = ReactAgent(user_profile=user_profile.model_dump())

    def chat_stream(self, query: str) -> Generator[str, None, None]:
        """
        Executes a chat session and yields response chunks.
        Args:
            query (str): The user's input/question.
        Yields:
            str: Content chunks for streaming.
        """
        profile_str = self._format_profile_for_agent()
        
        # We can also call make_decision here if we want to add intelligence 
        # to the routing before starting the full tool-calling loop.
        
        for chunk in self.agent_core.execute_stream(query, profile_str):
            yield chunk

    def _format_profile_for_agent(self) -> str:
        """Formats the UserProfile into a string format the agent understands."""
        return (
            f"【学生背景画像】\n"
            f"- 日语能力: {self.user_profile.jlpt_level}\n"
            f"- EJU预估分: {self.user_profile.eju_score}\n"
            f"- 本科GPA: {self.user_profile.gpa}\n"
            f"- 目标专业: {self.user_profile.target_major}\n"
            f"- 院校背景: {self.user_profile.undergraduate_school}\n"
            f"- 英语成绩: {self.user_profile.english_score}\n"
        )

# Example usage for testing/FastAPI:
if __name__ == "__main__":
    test_profile = UserProfile(
        jlpt_level="N1",
        eju_score=700,
        gpa=3.8,
        target_major="计算机科学",
        undergraduate_school="清华大学",
        english_score="TOEFL 105"
    )
    
    agent = HeadlessAgent(test_profile)
    for chunk in agent.chat_stream("请问我申请东京大学的机会大吗？"):
        print(chunk, end="", flush=True)
