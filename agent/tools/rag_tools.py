import hashlib
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger

RAW_CONTEXT_CACHE = {}

arg = RagSummarizeService()


class RagFetchContextInput(BaseModel):
    query: str = Field(description="具体的术语或搜索词，例如：'出愿资格'、'TOEFL要求'。如果搜寻某位教授（例如青木副教授），请务必只搜名字和核心研究（例如'青木 地震'），【绝对不要】加上'教授'、'副教授'等职称，否则无法命中。")


@tool("rag_fetch_context", args_schema=RagFetchContextInput)
def rag_fetch_context(query: str, state: Annotated[dict, InjectedState]) -> str:
    """
    【核心知识专用】当且仅当检索日本留学相关的硬核院校规章、专业录取政策、往年录取分数线、内部私域资料时调用此工具（如：东大笔试范围、早大出愿时间）。
    严重警告：绝不可以使用此工具搜寻广义的新闻、某教授的最新动态、或者互联网杂谈！
    如果连续找不到信息（返回了空或失败），请放弃并如实告知用户，严禁随意重试或自己编造。
    """
    messages = state.get("messages", [])
    extracted_profile = "暂无学生背景信息"
    if messages:
        first_msg = messages[0]
        content = getattr(first_msg, "content", "") if hasattr(first_msg, "content") else str(first_msg)
        if "【当前咨询者背景画像】" in content:
            extracted_profile = content

    cache_key = hashlib.md5(f"{query}_{extracted_profile}".encode()).hexdigest()

    if cache_key in RAW_CONTEXT_CACHE:
        logger.info(f"命中素材缓存: {query}")
        return f"参考资料(来自缓存)如下：\n{RAW_CONTEXT_CACHE[cache_key]}"

    try:
        logger.info(f"正在检索私有原始素材: {query}")
        raw_context = arg.get_raw_vector_context(query)
        RAW_CONTEXT_CACHE[cache_key] = raw_context
        logger.info(f"已获取私有素材 (长度: {len(raw_context)})，准备交给 Agent")
        return f"私域系统参考资料如下：\n{raw_context}"
    except Exception as e:
        logger.error(f"检索失败: {e}")
        return f"私域检索工具失败！详情：{str(e)}。请检查问题是否适合在私域找，如果是泛搜，请改用 web_search_tool。"
