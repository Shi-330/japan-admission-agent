from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from typing import Callable
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from utils.logger_handler import logger
from langchain.agents import AgentState  
from langgraph.runtime import Runtime
from utils.prompt_loader import load_system_prompts, load_report_prompts


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest, # 请求的函数封装
    handler: Callable[[ToolCallRequest], ToolMessage | Command], # 执行的函数本身
) -> ToolMessage | Command: # 工具执行的监控
    logger.info(f"[tool monitor]执行工具: {request.tool_call['name']}")    
    logger.info(f"[tool monitor]传入参数: {request.tool_call['args']}")    

    try:
        result = handler (request)
        logger.info(f"[tool monitor]工具{request.tool_call['name']}调用成功")

            
        if request.tool_call["name"] == "fill_context_for_report":
            if not hasattr(request.runtime, "context") or request.runtime.context is None:
                request.runtime.context = {}  # 初始化为一个空字典
            request.runtime.context["report"] = True
            logger.info("[Middleware] 已成功开启报告生成模式上下文")

        return result
    except Exception as e:
        logger.error(f"[tool monitor]工具{request.tool_call['name']}调用失败: {str(e)}")
        raise e

@before_model
def log_before_model(
    state: AgentState, # 整个Agent智能体中的状态记录
    runtime: Runtime, # 运行时，记录了整个执行过程中的上下文信息

): # 在模型执行前输出日志
    logger.info(f"[log_before_model]即将调用模型，带有: {len(state['messages'])}条消息")
    last_msg = state['messages'][-1]
    logger.debug(f"[log_before_model] {type(last_msg).__name__}|{last_msg.content.strip()}")

    return None


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    # 逐级安全获取：request -> runtime -> context
    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None) if runtime else None
    
    # 如果 context 存在则尝试 get "report"，否则默认为 False
    is_report = context.get("report", False) if context is not None else False
    
    if is_report:
        return load_report_prompts()
    
    return load_system_prompts()