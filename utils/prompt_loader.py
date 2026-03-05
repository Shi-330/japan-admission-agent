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

def load_system_prompts():
    prompt = get_active_prompt("system_prompt")
    if prompt: return prompt
    logger.error("重大错误：云端 System Prompt 加载失败且无本地备份！使用紧急兜底提示词。")
    return "你是一个专业的日本留学助手。目前云端指令加载异常，请在回答中提醒用户联系管理员。"

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