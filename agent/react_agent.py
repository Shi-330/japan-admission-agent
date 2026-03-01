from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_current_month, 
                                     generate_external_data, fetch_external_data, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch

class ReactAgent:
    def __init__(self, user_profile: dict = None):
        # 1. 加载原始系统提示词
        base_prompt = load_system_prompts()
        
        # 2. 如果传入了画像，构造增强提示词
        if user_profile:
            profile_context = f"""
            # 咨询者当前背景（请以此为准进行评估）：
            - 日语等级：{user_profile.get('jlpt', '未知')}
            - EJU分数：{user_profile.get('eju', '未知')}
            - 本科GPA：{user_profile.get('gpa', '未知')}
            - 目标专业：{user_profile.get('major', '未知')}
            ---
            """
            # 将画像拼接到 Prompt 头部，确保 Agent 第一时间看到
            system_prompt = profile_context + "\n" + base_prompt
        else:
            system_prompt = base_prompt

        self.agent = create_agent(
            model=chat_model,
            system_prompt=system_prompt, # 使用增强后的 Prompt
            tools=[rag_summarize, # get_user_id 这个之后再弄。 
                   get_current_month, generate_external_data, fetch_external_data, 
                   fill_context_for_report],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query: str, user_profile: dict = None):
        # 如果 user_profile 在这里也需要传递给某些 Tool，可以放入 context
        input_dict = {
            "messages":[
                {"role": "user", "content": query},
            ]
        }
        
        # 将 profile 放入 context 供 middleware 或某些 tool 使用
        agent_context = {"report": False, "user_profile": user_profile}

        for chunk in self.agent.stream(input_dict, stream_mode="values", context=agent_context):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"

if __name__ == "__main__":
    agent = ReactAgent()

    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="",flush=True)