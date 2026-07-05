from typing import AsyncGenerator
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools import (get_current_month, rag_fetch_context,
                          generate_external_data, fetch_external_data, fill_context_for_report,
                          update_report_suggestions, web_search_tool)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch, reset_tool_count
from .decision_engine import DecisionEngine
from utils.logger_handler import logger


def _extract_text(chunk) -> str:
    """Extract text from any possible stream chunk shape."""
    if isinstance(chunk, str):
        return chunk.strip()
    if isinstance(chunk, dict):
        return str(chunk.get("content", chunk.get("text", ""))).strip()
    if hasattr(chunk, "content"):
        c = chunk.content
        if isinstance(c, str):
            return c.strip()
        if isinstance(c, list):
            parts = []
            for sub in c:
                if isinstance(sub, dict):
                    parts.append(str(sub.get("text", sub.get("content", ""))))
                elif hasattr(sub, "text"):
                    parts.append(str(sub.text))
                else:
                    parts.append(str(sub))
            return "".join(parts).strip()
        return str(c).strip() if c else ""
    if isinstance(chunk, (list, tuple)):
        return "".join(_extract_text(item) for item in chunk)
    return ""


class ReactAgent:
    def __init__(self, user_profile: dict = None, cache_size: int = 100):
        base_prompt = load_system_prompts()
        
        if user_profile:
            profile_context = f"""
            # 咨询者当前背景：
            - 日语：{user_profile.get('jlpt_level', '未知')} | EJU：{user_profile.get('eju_score', '未知')}
            - GPA：{user_profile.get('gpa', '未知')} | 目标：{user_profile.get('target_major', '未知')}
            - 院校：{user_profile.get('undergraduate_school', '未知')} | 英语：{user_profile.get('english_score', '未知')}
            ---
            """
            system_prompt = profile_context + "\n" + base_prompt
        else:
            system_prompt = base_prompt

        self.model = chat_model 

        # 3. 初始化 Agent
        self.agent = create_agent(
            model=self.model,
            system_prompt=system_prompt,
            tools=[
                rag_fetch_context, # 核心瘦身工具
                web_search_tool,   # 新增的泛搜工具
                get_current_month, 
                generate_external_data, 
                fetch_external_data,
                fill_context_for_report,
                update_report_suggestions
            ],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

        self.decision_engine = DecisionEngine(cache_size=cache_size)

    def make_decision(self, planner_prompt_template: str = None,
                      profile_string: str = None, user_input: str = None) -> str:
        return self.decision_engine.classify(planner_prompt_template, profile_string, user_input)

    async def execute_stream(self, query: str, user_profile_str: str = None) -> AsyncGenerator[str, None]:
        if not self.agent:
            yield {"content": "Agent initialization failed", "is_status": False, "done": True}
            return

        messages = []
        if user_profile_str:
            profile_instruction = f"【当前咨询者背景画像】\n{user_profile_str}\n请务必参考此背景。"
            messages.append(HumanMessage(content=profile_instruction)) # Treat as human message to not confuse system prompt
        messages.append(HumanMessage(content=query))

        state = {
            "messages": messages,
            "chat_history": []
        }
        
        reset_tool_count()
        try:
            async for event in self.agent.astream_events(state, config={"callbacks": [], "recursion_limit": 15}, version="v2"):
                kind = event["event"]
                name = event.get("name", "")

                # --- Status events ---
                if kind == "on_chat_model_start" or (kind == "on_chain_start" and name == "model"):
                    yield {"content": "[STATUS:THINKING]", "is_status": True, "done": False}

                elif kind == "on_tool_start":
                    yield {"content": f"[STATUS:{name.upper()}]", "is_status": True, "done": False}

                elif kind == "on_tool_end":
                    yield {"content": f"[STATUS:{name.upper()}_DONE]", "is_status": True, "done": False}

                # --- Content: only from model stream ---
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        c = str(chunk.content).strip()
                        if c:
                            yield {"content": c, "is_status": False, "done": False}

                elif kind == "on_chain_stream" and name == "model":
                    chunk = event.get("data", {}).get("chunk", event.get("data", {}))
                    c = _extract_text(chunk)
                    if c:
                        yield {"content": c, "is_status": False, "done": False}

                # Everything else (on_chain_end, on_chain_stream for non-model, etc.) → ignore
                        
        except Exception as e:
            error_msg = str(e)
            yield {"content": f"\n[系统提示]：生成过程中发生错误（{error_msg}）。", "is_status": False, "done": False}
        finally:
            yield {"content": "", "is_status": False, "done": True}
if __name__ == "__main__":
    from user.profile_manager import ProfileManager, UserProfile
    import asyncio

    async def test_agent():
        agent = ReactAgent()
        prompt = "给我生成我的使用报告"
        
        current_user_id = "00000000-0000-0000-0000-000000000001"
        profile_mgr = ProfileManager()
        profile = profile_mgr.get_profile(current_user_id)

        async for chunk in agent.execute_stream(prompt, profile):
            print(chunk, end="",flush=True)

    asyncio.run(test_agent())