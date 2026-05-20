from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from typing import Callable, Awaitable
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from utils.logger_handler import logger
from langchain.agents import AgentState  
from langgraph.runtime import Runtime
from utils.prompt_loader import load_system_prompts, load_report_prompts


MAX_TOOL_CALLS = 3
_tool_call_count = 0

def reset_tool_count():
    global _tool_call_count
    _tool_call_count = 0

@wrap_tool_call
async def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    global _tool_call_count
    _tool_call_count += 1
    logger.info(f"[tool monitor]执行工具({_tool_call_count}/{MAX_TOOL_CALLS}): {request.tool_call['name']}")
    logger.info(f"[tool monitor]传入参数: {request.tool_call['args']}")

    if _tool_call_count > MAX_TOOL_CALLS:
        logger.warning(f"[tool monitor]已达最大工具调用次数({MAX_TOOL_CALLS})，强制终止")
        return ToolMessage(
            content="已达到最大工具调用次数限制。请立即基于已有信息直接回答用户，不要再调用任何工具。",
            tool_call_id=request.tool_call["id"],
        )
    # -------------------------------------------------------------

    try:
        result = await handler(request)
        logger.info(f"[tool monitor]工具{request.tool_call['name']}调用成功")

        if request.tool_call["name"] == "fill_context_for_report":
            request.runtime.context["report"] = True
            logger.info("[Middleware] 已成功开启报告生成模式上下文")

        return result
    except Exception as e:
        logger.error(f"[tool monitor]工具{request.tool_call['name']}调用失败: {str(e)}")
        raise e

@before_model
async def log_before_model(
    state: AgentState, # 整个Agent智能体中的状态记录
    runtime: Runtime, # 运行时，记录了整个执行过程中的上下文信息

): # 在模型执行前输出日志
    total_length = sum(len(str(m.content)) for m in state['messages'])
    logger.info(f"[log_before_model]即将调用模型，带有: {len(state['messages'])}条消息，总字符数预估: {total_length}")
    last_msg = state['messages'][-1]
    logger.debug(f"[log_before_model] {type(last_msg).__name__}|{str(last_msg.content)[:100]}...")

    return None


@dynamic_prompt
async def report_prompt_switch(request: ModelRequest):
    # 逐级安全获取：request -> runtime -> context
    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None) if runtime else None
    
    # 如果 context 存在则尝试 get "report"，否则默认为 False
    is_report = context.get("report", False) if context is not None else False
    
    if is_report:
        return load_report_prompts()
    
    return load_system_prompts()
