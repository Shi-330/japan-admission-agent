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

def _load_local_prompt(config_key: str):
    try:
        prompt_path = get_abs_path(prompts_conf[config_key])
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"加载本地提示词 ({config_key}) 出错: {str(e)}")
        raise e

def load_system_prompts():
    prompt = get_active_prompt("system_prompt")
    if prompt: return prompt
    return _load_local_prompt("main_prompt_path")

def load_rag_prompts():
    prompt = get_active_prompt("rag_prompt")
    if prompt: return prompt
    return _load_local_prompt("rag_summarize_prompt_path")

def load_report_prompts():
    prompt = get_active_prompt("report_prompt")
    if prompt: return prompt
    return _load_local_prompt("report_prompt_path")

if __name__ == "__main__":
    print(load_system_prompts())