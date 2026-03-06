import json
import os
import random
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from supabase import create_client, Client

from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger
import dotenv
import hashlib

_supabase_client = None     # 延迟初始化单例模式

# 定义一个简单的内存缓存（如果 query 没变，直接秒回）
# 对于 SaaS，之后可以把这部分换成 Redis
RAW_CONTEXT_CACHE = {}

def get_supabase() -> Client:
    """确保在工具被调用时才初始化 Supabase，并确保环境变量已加载"""
    global _supabase_client
    if _supabase_client is None:
        # 手动确保加载 .env（使用你的 path_tool）
        env_path = get_abs_path(".env")
        dotenv.load_dotenv(env_path)
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not url or not key:
            # 这里的报错会更清晰
            raise ValueError(f"Supabase 配置缺失! URL: {url}, Key: {'已找到' if key else '缺失'}")
        
        _supabase_client = create_client(url, key)
    return _supabase_client

# --- 2. 业务服务初始化 ---
# 建议也放进函数或延迟初始化，防止 RagSummarizeService 内部也依赖环境

_external_data = {}          # 缓存数据
_data_loaded = False         # 标记是否已加载数据

arg = RagSummarizeService()
#user_ids = "00000000-0000-0000-0000-000000000001" #更换为默认的这个uuid["1001","1002","1003","1004","1005","1006","1007","1008","1009","1010"]
month_arr = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06","2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]
external_data = {}

from pydantic import BaseModel, Field

# --- Pydantic Schemas for Strict Tool Inputs ---

class FetchUserProfileInput(BaseModel):
    user_id: str = Field(description="用户的唯一标识符 UUID (例如 '00000000-0000-0000-0000-000000000001')")

class RagFetchContextInput(BaseModel):
    query: str = Field(description="具体的术语或搜索词，例如：'出愿资格'、'TOEFL要求'。如果搜寻某位教授（例如青木副教授），请务必只搜名字和核心研究（例如'青木 地震'），【绝对不要】加上'教授'、'副教授'等职称，否则无法命中。")

class FetchExternalDataInput(BaseModel):
    user_id: str = Field(description="用户的唯一标识符 UUID")
    month: str = Field(description="月份，格式必须为 YYYY-MM，如 '2025-03'")


@tool("fetch_user_profile_from_db", args_schema=FetchUserProfileInput)
def fetch_user_profile_from_db(user_id: str) -> str:
    """
    当需要了解当前咨询者的真实背景（例如日语成绩、GPA、出身校等）时调用此工具。
    如果不提供 user_id，默认尝试不调用或使用占位符。
    """
    client = get_supabase() 
    try:
        response = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return str(response.data) if response.data else "未查找到该用户的背景画像。请提示用户补充资料。"
    except Exception as e:
        logger.error(f"从数据库获取画像失败: {e}")
        return f"工具调用失败，无法获取背景信息: {str(e)}。请继续使用已有信息回答，不要重试。"

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
        print(f"⚡ [Cache Hit] 命中素材缓存: {query}")
        return f"参考资料(来自缓存)如下：\n{RAW_CONTEXT_CACHE[cache_key]}"

    try: 
        print(f"🔍 [Private RAG Fetching] 正在检索私有原始素材: {query}")
        raw_context = arg.get_raw_vector_context(query) 
        
        RAW_CONTEXT_CACHE[cache_key] = raw_context
        print(f"⚡ [Context Fetched] 已获取私有素材 (长度: {len(raw_context)})，准备交给 Agent")
        return f"私域系统参考资料如下：\n{raw_context}"
        
    except Exception as e:
        logger.error(f"检索失败: {e}")
        return f"私域检索工具失败！详情：{str(e)}。请检查问题是否适合在私域找，如果是泛搜，请改用 web_search_tool。"

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
        print(f"⚡ [Cache Hit] 命中外网检索缓存: {query}")
        return f"互联网检索结果(来自缓存)如下：\n{WEB_SEARCH_CACHE[cache_key]}"
        
    try:
        from langchain_community.tools import DuckDuckGoSearchResults
        from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
        print(f"🌐 [Web Search] 正在联网检索外网: {query}")
        
        # 使用 DDGS 获取带片段的结果
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
    return random.choice(month_arr)

def _load_external_data():
    """内部函数：加载外部数据到 _external_data 字典"""
    global _external_data, _data_loaded
    if _data_loaded:
        return

    external_data_path = get_abs_path(agent_conf["external_data_path"])
    if not os.path.exists(external_data_path):
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    with open(external_data_path, "r", encoding="utf-8") as f:
        for line in f.readlines()[1:]:
            arr = line.strip().split(",")
            user_id = arr[0].replace('"', '')
            feature = arr[1].replace('"', '')
            efficiency = arr[2].replace('"', '')
            consumables = arr[3].replace('"', '')
            comparison = arr[4].replace('"', '')
            time = arr[5].replace('"', '')

            if user_id not in _external_data:
                _external_data[user_id] = {}

            _external_data[user_id][time] = {
                "特征": feature,
                "效率": efficiency,
                "消耗": consumables,
                "对比": comparison,
            }
    _data_loaded = True

@tool("generate_external_data")
def generate_external_data() -> str:
    """无入参。获取当前系统中记录的所有用户的全家桶使用行为数据（返回 JSON 格式的字符串）。"""
    _load_external_data()
    return json.dumps(_external_data, ensure_ascii=False)

class UpdateReportSuggestionsInput(BaseModel):
    user_id: str = Field(description="用户的唯一标识符 UUID")
    new_suggestions: str = Field(description="更新后的核心建议内容。注意：这会覆盖原有的建议内容，请传入完整的一套建议。")

@tool("update_report_suggestions", args_schema=UpdateReportSuggestionsInput)
def update_report_suggestions(user_id: str, new_suggestions: str) -> str:
    """
    【强制要求】报告规划生成完毕后，或者你认为需要调整用户的升学规划时，必须【立刻且必然】调用此工具。
    这将把你的核心建议保存到云端数据库中，非常重要！否则用户的看板将永远为空。
    """
    client = get_supabase()
    try:
        # Pydantic 工具调用保护
        response = client.table("user_profiles").update({
            "suggestions": new_suggestions,
            "report_status": "REFINED" # 标记为已被精调
        }).eq("id", user_id).execute()
        return "报告建议库已成功更新。你可以回复用户，告诉他们看板上的建议已经刷新。"
    except Exception as e:
        logger.error(f"更新报告建议失败: {e}")
        return f"工具调用失败，无法更新建议: {str(e)}。请告知用户数据库发生异常。"

@tool("fetch_external_data", args_schema=FetchExternalDataInput)
def fetch_external_data(user_id: str, month: str) -> str:
    """
    明确查询某个用户在特定月份的系统使用记录时调用。
    注意：只允许查询格式为 YYYY-MM 的月份。如果返回空结果，说明该月无记录，不要更换无效格式重试。
    """
    _load_external_data()
    try:
        data = _external_data[user_id][month]
        # 格式化为多行文本
        lines = [f"{k}: {v}" for k, v in data.items()]
        return "\n".join(lines)
    except KeyError:
        logger.warning(f"[fetch_external_data] 未找到用户 {user_id} 在 {month} 的记录")
        return f"查询成功，系统内无用户 {user_id} 在 {month} 的相关数据记录。请直接回复用户无数据。"
    except Exception as e:
        return f"工具查询异常: {str(e)}。请放弃本次调用。"

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为提示词切换提供上下文信息")
def fill_context_for_report():
    """
    此工具主要作为一个 'Signal' (信号)。
    Agent 调用它意味着它现在想要进入 '报告生成模式'。
    【重要提醒】：生成完报告后，请记得一定要调用 `update_report_suggestions` 来把建议提炼并固化到数据库！
    """
    return "fill_context_for_report已调用，中间件已感知并切换提示词逻辑"