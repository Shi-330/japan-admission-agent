import hashlib
import cachetools
from datetime import datetime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from utils.logger_handler import logger

WEB_SEARCH_CACHE = cachetools.TTLCache(maxsize=200, ttl=1800)  # 200 entries, 30-min TTL


class WebSearchInput(BaseModel):
    query: str = Field(description="互联网检索词。必须精简！如搜人请用'东京大学 青木 地震研究'，【绝对不要】带'教授'、'副教授'等头衔干扰搜索。")


def web_search(query: str, max_results: int = 3, region: str = None, timelimit: str = None) -> list[dict]:
    """
    Standalone DuckDuckGo web search returning structured results.

    Args:
        query: Search query string.
        max_results: Maximum number of results (default 3).
        region: Optional region code (e.g. "jp-jp"). None = no region filter.
        timelimit: Optional time filter ("d"/"w"/"m"/"y"). None = no time filter.

    Returns:
        list[dict]: Each dict has keys {title, url, snippet}.
        Returns empty list on any error (network, timeout, no results).
        Never raises an exception.
    """
    cache_key = hashlib.md5(f"web_search:{query}:{max_results}:{region}:{timelimit}".encode()).hexdigest()
    cached = WEB_SEARCH_CACHE.get(cache_key)
    if cached is not None:
        logger.info(f"Web search cache hit: {query[:40]}")
        return cached

    try:
        from duckduckgo_search import DDGS
        logger.info(f"Web search: {query[:60]} (max_results={max_results}, region={region}, timelimit={timelimit})")
        results = []
        with DDGS() as ddgs:
            kwargs = {"max_results": max_results}
            if region:
                kwargs["region"] = region
            if timelimit:
                kwargs["timelimit"] = timelimit
            for r in ddgs.text(query, **kwargs):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
                if len(results) >= max_results:
                    break
        if results:
            WEB_SEARCH_CACHE[cache_key] = results
        return results
    except Exception as e:
        logger.warning(f"Web search failed for '{query[:40]}': {e}")
        return []


@tool("web_search_tool", args_schema=WebSearchInput)
def web_search_tool(query: str) -> str:
    """
    【全网泛搜专用】当你需要获取某个具体教授的最新动态、最近的新闻政策、或者任何不在硬核手册里的话题时，请调用此工具。
    比如写套磁信前，你可以用此工具去网上爬取目标教授的研究方向和最新动态。
    """
    try:
        logger.info(f"正在联网检索外网: {query}")
        results = web_search(query, max_results=4, region="jp-jp", timelimit="y")
        if not results:
            return "互联网搜索未找到相关结果，请尝试更换关键词。"
        text = "\n".join(f"{r['title']}: {r['snippet'][:200]} (来源: {r['url']})" for r in results)
        return f"互联网检索结果如下：\n{text}"
    except Exception as e:
        logger.error(f"外网检索失败: {e}")
        return f"外网检索失败: {str(e)}。无法连接外网，请告知用户我们目前只能依靠私有知识库。"


@tool("get_current_month")
def get_current_month() -> str:
    """无入参。获取当前的月份（如 '2025-03'）。当你需要计算距离某个考试还有几个月时，可以调用。"""
    return datetime.now().strftime("%Y-%m")
