from cachetools import func
from utils.supabase_client import supabase
from utils.logger_handler import logger
from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path

@func.ttl_cache(maxsize=128, ttl=3600)
def get_active_prompt(prompt_name: str) -> str:
    """从 Supabase 云端拉取当前激活的 Prompt"""
    try:
        response = supabase.table("prompts") \
                           .select("template_text") \
                           .eq("name", prompt_name) \
                           .eq("is_active", True) \
                           .execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["template_text"]
        else:
            logger.warning(f"未在云端找到启用的 {prompt_name} 模板！尝试本地 fallback。")
            return None
    except Exception as e:
        logger.error(f"拉取云端 Prompt 失败: {str(e)}")
        return None

FALLBACK_SYSTEM_PROMPT = """你是一位专业的日本留学升学顾问。

## 可用工具（共5个，只能用这5个）
- rag_fetch_context(query: str) — 检索私塾内部知识库
- web_search_tool(query: str) — 搜索互联网公开信息
- get_current_month() — 获取当前月份
- fill_context_for_report() — 进入报告生成模式
- update_report_suggestions(user_id, new_suggestions) — 保存报告建议

## 核心规则（必须遵守）
1. 最多调用2次工具，之后必须直接回答用户。
2. rag_fetch_context 搜不到就回复"知识库暂未收录此信息，建议咨询私塾老师"，严禁换词重试。
3. web_search_tool 超时或失败就跳过，不要重试。
4. 绝对不要编造工具名。你只有上述5个工具。
5. 用简洁中文回答，不要废话。"""

def load_system_prompts():
    prompt = get_active_prompt("system_prompt")
    if prompt: return prompt
    logger.warning("云端 System Prompt 加载失败，使用本地备用 prompt。")
    return FALLBACK_SYSTEM_PROMPT

def load_rag_prompts():
    prompt = get_active_prompt("rag_prompt")
    if prompt: return prompt
    return "请根据以下资料回答用户的问题。如果资料中未提及，请如实告知。"

def load_report_prompts():
    prompt = get_active_prompt("report_prompt")
    if prompt: return prompt
    return "你现在的任务是为学生生成一份升学规划建议看板。"

if __name__ == "__main__":
    print(load_system_prompts())
    test_res = supabase.table("prompts").select("*").execute()
    print("数据库连接测试:", test_res.data)