import hashlib
from datetime import datetime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from utils.logger_handler import logger

WEB_SEARCH_CACHE = {}


class WebSearchInput(BaseModel):
    query: str = Field(description="互联网检索词。必须精简！如搜人请用'东京大学 青木 地震研究'，【绝对不要】带'教授'、'副教授'等头衔干扰搜索。")


@tool("web_search_tool", args_schema=WebSearchInput)
def web_search_tool(query: str) -> str:
    """
    【全网泛搜专用】当你需要获取某个具体教授的最新动态、最近的新闻政策、或者任何不在硬核手册里的话题时，请调用此工具。
    比如写套磁信前，你可以用此工具去网上爬取目标教授的研究方向和最新动态。
    """
    cache_key = hashlib.md5(query.encode()).hexdigest()
    if cache_key in WEB_SEARCH_CACHE:
        logger.info(f"命中外网检索缓存: {query}")
        return f"互联网检索结果(来自缓存)如下：\n{WEB_SEARCH_CACHE[cache_key]}"

    try:
        from langchain_community.tools import DuckDuckGoSearchResults
        from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
        logger.info(f"正在联网检索外网: {query}")
        wrapper = DuckDuckGoSearchAPIWrapper(region="jp-jp", time="y", max_results=4)
        search_tool = DuckDuckGoSearchResults(api_wrapper=wrapper)
        results = search_tool.invoke(query)
        if not results:
            return "互联网搜索未找到相关结果，请尝试更换关键词。"
        WEB_SEARCH_CACHE[cache_key] = results
        return f"互联网检索结果如下：\n{results}"
    except Exception as e:
        logger.error(f"外网检索失败: {e}")
        return f"外网检索失败: {str(e)}。无法连接外网，请告知用户我们目前只能依靠私有知识库。"


@tool("get_current_month")
def get_current_month() -> str:
    """无入参。获取当前的月份（如 '2025-03'）。当你需要计算距离某个考试还有几个月时，可以调用。"""
    return datetime.now().strftime("%Y-%m")
