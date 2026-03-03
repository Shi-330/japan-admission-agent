from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_current_month, get_user_id,
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

        self.model = chat_model # 将模型实例挂载到 self 上，方便外部或内部调用


        self.agent = create_agent(
            model=self.model, #  chat_model -> 这里也改用 self.model
            system_prompt=system_prompt, # 使用增强后的 Prompt
            tools=[rag_summarize, # get_user_id 这个之后再弄。 
                   get_current_month, generate_external_data, fetch_external_data, get_user_id,
                   fill_context_for_report],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )
    def make_decision(self, planner_prompt_template: str = None, profile_string: str = None, user_input: str = None) -> str:
        """
        让LLM在不启动工具流的情况下，先做一个快速的意图判断
        """
        # 填充模板
        full_prompt = planner_prompt_template.format(
            profile_string=profile_string, 
            user_input=user_input
            )
        
        # 直接调用底层的LLM(chat_model)
        # 注意：取决于你的 chat_model 是 LangChain 的什么对象，
        # 通常调用 invoke 或 predict。对于最新的 LangChain，建议用 invoke。
        try:
            response = self.model.invoke(full_prompt)
            # 提取文本内容
            if hasattr(response, "content"):
                return response.content
            return str(response)
        
        except Exception as e:
            print(f"[Decision Error] 决策引擎故障: {e}")
            return "[ANSWER]" # 发生错误时默认走常规回答路径

     
    def execute_stream(self, query: str, user_profile_str: str = None):
        # 构造消息序列
        messages = []
        
        # 1. 把画像作为第一条系统消息强行插入，这样它就永远在 messages 状态里了
        if user_profile_str:
            profile_instruction = f"【当前咨询者背景画像】\n{user_profile_str}\n请务必参考此背景进行回答和调用工具。"
            messages.append({"role": "system", "content": profile_instruction})
        
        messages.append({"role": "user", "content": query})

        input_dict = {
            "messages": messages  # 现在我们只传 messages，因为保安只认它
        }
        # 【调试点 2】确认 input_dict 的结构
        print(f"\n[DEBUG 2 - Agent] 构建的 input_dict 键值: {list(input_dict.keys())}")
        print(f"[DEBUG 2 - Agent] 构建的 input_dict 内容: {input_dict}")
        # 执行流
        # for chunk in self.agent.stream(input_dict, stream_mode="values"):
        #     if "messages" in chunk and chunk["messages"]:
        #         latest_message = chunk["messages"][-1]
        #         # 注意：LangGraph 返回的可能是 BaseMessage 对象，使用 .content 获取内容
        #         if hasattr(latest_message, "content") and latest_message.content:
        #             yield latest_message.content.strip() + "\n"
        # 执行流
        last_seen_len = 0
        for chunk in self.agent.stream(input_dict, stream_mode="values"):
            if "messages" in chunk:
                all_messages = chunk["messages"]
                # 只取新产生的消息
                if len(all_messages) > last_seen_len:
                    new_messages = all_messages[last_seen_len:]
                    for msg in new_messages:
                        # 过滤掉空的或者 AI 正在思考的消息，只返回文本内容
                        content = getattr(msg, "content", str(msg))
                        if content:
                            yield content.strip() + "\n"
                    last_seen_len = len(all_messages)        

if __name__ == "__main__":
    from user.profile_manager import ProfileManager, UserProfile

    agent = ReactAgent()
    prompt = "给我生成我的使用报告"
    
    current_user_id = "00000000-0000-0000-0000-000000000001"
    profile_mgr = ProfileManager()
    profile = profile_mgr.get_profile(current_user_id)

    for chunk in agent.execute_stream(prompt, profile):
        print(chunk, end="",flush=True)