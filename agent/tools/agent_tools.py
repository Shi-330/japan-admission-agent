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

@tool(description="从外部系统中获取用户画像，以纯字符串形式返回，如果未检索到，返回空字符串")
def fetch_user_profile_from_db(user_id: str):
    """从 Supabase 获取真实的留学背景画像"""
    # 调用封装好的单例获取 client
    client = get_supabase() 
    try:
        response = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return response.data  
    except Exception as e:
        logger.error(f"从数据库获取画像失败: {e}")
        return ""

# @tool(description="从向量存储中检索参考资料，并结合用户画像给出个性化建议")
# def rag_summarize(query: str, state: Annotated[dict, InjectedState]) -> str:
# # 1. 从 state 中获取所有消息
#     messages = state.get("messages", [])
    
#     # 2. 尝试从第一条系统消息中提取画像信息
#     # 逻辑：我们在 execute_stream 里把画像放在了第一条 system message
#     extracted_profile = "暂无学生背景信息"
    
#     if messages:
#         # 兼容 LangChain 的 Message 对象格式
#         first_msg = messages[0]
#         # 有时 messages 是字典对象，有时是 BaseMessage 对象
#         content = ""
#         if isinstance(first_msg, dict):
#             if first_msg.get("role") == "system":
#                 content = first_msg.get("content", "")
#         else:
#             # 这里的 getattr 是为了处理 LangGraph 传入的可能是 SystemMessage 对象
#             if getattr(first_msg, "type", "") == "system" or hasattr(first_msg, "content"):
#                 content = getattr(first_msg, "content", "")

#         if "【当前咨询者背景画像】" in content:
#             extracted_profile = content
            
#     # print(f"\n[DEBUG 3 - Tool] 当前 State 中的所有键: {list(state.keys())}")
#     # print(f"DEBUG: Tool 最终拿到的画像: {extracted_profile[:50]}...") 
    
#     # 3. 将提取到的画像传入真正的 RAG 服务
#     return arg.rag_summarize(query, extracted_profile)

@tool(description="检索日本留学相关的院校、专业及政策原始资料")
def rag_fetch_context(query: str, state: Annotated[dict, InjectedState]) -> str:
    # 1. 提取画像信息 (逻辑保持不变)
    messages = state.get("messages", [])
    extracted_profile = "暂无学生背景信息"
    if messages:
        first_msg = messages[0]
        content = getattr(first_msg, "content", "") if hasattr(first_msg, "content") else str(first_msg)
        if "【当前咨询者背景画像】" in content:
            extracted_profile = content

    # 2. 【关键减负】构建缓存 Key (Query + Profile)
    cache_key = hashlib.md5(f"{query}_{extracted_profile}".encode()).hexdigest()
    
    # 如果命中缓存，直接秒回素材
    if cache_key in RAW_CONTEXT_CACHE:
        print(f"⚡ [Cache Hit] 命中素材缓存: {query}")
        return f"参考资料(来自缓存)如下：\n{RAW_CONTEXT_CACHE[cache_key]}"

    # 3. 执行真正的“轻量化”检索
    try: 
        print(f"🔍 [Fetching Context] 正在检索原始素材: {query}")
        # 注意：这里调用的是纯检索函数，不再是耗时 100s 的 summarize
        raw_context = arg.get_raw_vector_context(query) 
        
        # 存入缓存
        RAW_CONTEXT_CACHE[cache_key] = raw_context
        
        print(f"⚡ [Context Fetched] 已获取素材，准备交给 Agent 实时流式总结")
        return f"参考资料如下：\n{raw_context}"
        
    except Exception as e:
        # 如果底层没有 get_raw_vector_context，这里会报错，提醒你去底层服务里拆分函数
        return f"检索失败，请检查底层 arg 服务是否支持纯检索: {e}"

# @tool(description="获取用户的ID，以纯字符串形式返回")
# def get_user_id() -> str:
#     """获取当前登录用户的唯一标识符 (UUID)"""
#     # 暂时返回固定测试 ID，方便开发调试
#     # TODO: 后续接入真实登录系统后，从 session 或上下文获取
#     return "00000000-0000-0000-0000-000000000001"

@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
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

@tool(description="从外部系统中获取用户的使用记录，以纯字符串形式返回，如果未检索到，返回空字符串")
def generate_external_data() -> str:
    _load_external_data()
    return json.dumps(_external_data, ensure_ascii=False)
    """
    {
        "user_id": {   
            "month": {"特征":"值", "效率": "值", ... }
            "month": {"特征":"值", "效率": "值", ... }
            "month": {"特征":"值", "效率": "值", ... }
            ...
        },
        "user_id": {   
            "month": {"特征":"值", "效率": "值", ... }
            "month": {"特征":"值", "效率": "值", ... }
            "month": {"特征":"值", "效率": "值", ... }
            ...
        },
                "user_id": {   
            "month": {"特征":"值", "效率": "值", ... }
            "month": {"特征":"值", "效率": "值", ... }
            "month": {"特征":"值", "效率": "值", ... }
            ...
        },
    }:
    return 
    
    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data_path"])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")
        
        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")

                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                        "特征": feature,
                        "效率": efficiency,
                        "消耗": consumables,
                        "对比": comparison,
                }
                        """

@tool(description="获取指定用户和月份的使用记录，以纯文本格式返回，若不存在则返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    _load_external_data()
    try:
        data = _external_data[user_id][month]
        # 格式化为多行文本
        lines = [f"{k}: {v}" for k, v in data.items()]
        return "\n".join(lines)
    except KeyError:
        logger.warning(f"[fetch_external_data] 未找到用户 {user_id} 在 {month} 的记录")
        return ""

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为提示词切换提供上下文信息")
def fill_context_for_report():
    """
    此工具主要作为一个 'Signal' (信号)。
    Agent 调用它意味着它现在想要进入 '报告生成模式'。
    """
    return "fill_context_for_report已调用，中间件已感知并切换提示词逻辑"