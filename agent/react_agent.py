import hashlib
from typing import Dict, Any, Optional, AsyncGenerator
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (get_current_month,rag_fetch_context,
                                     generate_external_data, fetch_external_data, fill_context_for_report,
                                     update_report_suggestions, web_search_tool)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from .memory import DecisionCache
from utils.logger_handler import logger

class ReactAgent:
    def __init__(self, user_profile: dict = None, cache_size: int = 100):
        # 1. 确保工具被正确导入 (注意：这里要包含我们刚写的 rag_fetch_context)
        from agent.tools.agent_tools import (
            rag_fetch_context, # 换成瘦身后的工具
            get_current_month, 
            generate_external_data, 
            fetch_external_data, 
            fill_context_for_report,
            update_report_suggestions,
            web_search_tool
        )
        
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

        self.memory = DecisionCache(max_size=cache_size)

    def make_decision(self, 
                      planner_prompt_template: str = None, 
                      profile_string: str = None, 
                      user_input: str = None,) -> str:
        """
        让LLM在不启动工具流的情况下，先做一个快速的意图判断
        新增external_cache，带缓存的带缓存的快速意图判断。 external_cache: 外部传入的缓存字典（例如 Streamlit 的 session_state）
        """
        # 1. 内部处理缓存键生成
        cache_key = self.memory.generate_key(profile_string, user_input)

        # 2. 内部查询缓存，不再向外面（Streamlit）要数据
        cached_res = self.memory.get(cache_key)
        if cached_res:
            logger.info(f"决策缓存命中: {cache_key}")
            return cached_res

        full_prompt = planner_prompt_template.format(
            profile_string=profile_string,
            user_input=user_input,
        )
        

        try:
            logger.info(f"执行决策LLM调用: {cache_key}")
            response = self.model.invoke(full_prompt)
            result = response.content if hasattr(response, "content") else str(response)

            self.memory.set(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"决策引擎故障: {e}")
            return "[ANSWER]" # 发生错误时默认走常规回答路径

     
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
        
        try:
            # We must use astream_events with version="v2" to get token-by-token streaming
            # The 'model' node must not be stripped of the `RunnableConfig` by LangChain's create_agent bug.
            async for event in self.agent.astream_events(state, config={"callbacks": [], "recursion_limit": 100}, version="v2"):
                kind = event["event"]
                # Map LangGraph events to our simplified status markers or content
                
                # Model started generating
                if kind == "on_chat_model_start":
                    yield {"content": "[STATUS:THINKING]", "is_status": True, "done": False}
                    
                # Model streaming tokens
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        content_str = str(chunk.content)
                        if content_str.strip():
                            yield {"content": content_str, "is_status": False, "done": False}
                            
                # Tool execution started
                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    if tool_name == "rag_fetch_context":
                        yield {"content": "[STATUS:RETRIEVING]", "is_status": True, "done": False}
                    else:
                        yield {"content": f"[STATUS:TOOL_{tool_name.upper()}]", "is_status": True, "done": False}
                        
                # Tool execution ended
                elif kind == "on_tool_end":
                    tool_name = event["name"]
                    if tool_name == "rag_fetch_context":
                        yield {"content": "[STATUS:RETRIEVING_DONE]", "is_status": True, "done": False}
                        
        except Exception as e:
            error_msg = str(e)
            yield {"content": f"\n⚠️ [系统提示]：生成过程中发生错误（{error_msg}）。", "is_status": False, "done": False}
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