import hashlib
from typing import Dict, Any, Optional
from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (get_current_month,rag_fetch_context,
                                     generate_external_data, fetch_external_data, fill_context_for_report,
                                     update_report_suggestions, web_search_tool)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from .memory import DecisionCache

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
            - 日语：{user_profile.get('jlpt', '未知')} | EJU：{user_profile.get('eju', '未知')}
            - GPA：{user_profile.get('gpa', '未知')} | 目标：{user_profile.get('major', '未知')}
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
            print(f"[Internal Cache Hit] {cache_key}")
            return cached_res

        full_prompt = planner_prompt_template.format(
            profile_string=profile_string,
            user_input=user_input,
        )
        

        try:
            print(f"☁️ [LLM CALL] 正在进行决策... {cache_key}")
            response = self.model.invoke(full_prompt)
            result = response.content if hasattr(response, "content") else str(response)

            self.memory.set(cache_key, result)
            return result
        
        except Exception as e:
            print(f"[Decision Error] 决策引擎故障: {e}")
            return "[ANSWER]" # 发生错误时默认走常规回答路径

     
    def execute_stream(self, query: str, user_profile_str: str = None):
        messages = []
        if user_profile_str:
            profile_instruction = f"【当前咨询者背景画像】\n{user_profile_str}\n请务必参考此背景。"
            messages.append({"role": "system", "content": profile_instruction})
        
        messages.append({"role": "user", "content": query})

        yield "[STATUS:UNDERSTANDING]"
        
        # 使用 stream_mode="updates" 以捕捉工具调用和中间状态
        # 这种模式下 chunk 是一个 dict，例如 {"agent": {"messages": [...]}} 或 {"tools": {"messages": [...]}}
        try:
            for chunk in self.agent.stream({"messages": messages}, stream_mode="updates"):
                # A. 检查工具调用 (Retrieving)
                if "tools" in chunk:
                    yield "[STATUS:RETRIEVING]"
                    # 如果工具执行中发生错误，可以在这里扩展捕获，但通常工具内部已有 try-except
                
                # B. 检查 Agent 决策 (Thinking)
                if "agent" in chunk:
                    # 如果即将产生 AI 消息
                    latest_msg = chunk["agent"]["messages"][-1]
                    if hasattr(latest_msg, "tool_calls") and latest_msg.tool_calls:
                        # 正在决定使用工具
                        yield "[STATUS:THINKING]"
                    elif hasattr(latest_msg, "content") and latest_msg.type == "ai":
                        # 开始生成最终回复
                        yield "[STATUS:GENERATING]"
                        if latest_msg.content:
                            yield latest_msg.content

        except Exception as e:
            # Error Handling: 拦截工具调用错误，转化为用户友好的提示
            friendly_err = f"\n⚠️ [系统提示]：由于网络或知识库连接波动，我暂时无法获取最新院校数据（错误详情：{str(e)}）。请直接告诉我你的成绩和意向，我将基于已有知识为你分析。"
            yield friendly_err
            print(f"[Stream Error] {e}")
if __name__ == "__main__":
    from user.profile_manager import ProfileManager, UserProfile

    agent = ReactAgent()
    prompt = "给我生成我的使用报告"
    
    current_user_id = "00000000-0000-0000-0000-000000000001"
    profile_mgr = ProfileManager()
    profile = profile_mgr.get_profile(current_user_id)

    for chunk in agent.execute_stream(prompt, profile):
        print(chunk, end="",flush=True)