from model.factory import chat_model
from .memory import DecisionCache
from utils.logger_handler import logger


class DecisionEngine:
    """Pre-execution intent classifier. Cached (LRU+TTL) to avoid redundant LLM calls."""

    def __init__(self, cache_size: int = 100):
        self.model = chat_model
        self.cache = DecisionCache(max_size=cache_size)

    def classify(self, planner_prompt_template: str, profile_string: str, user_input: str) -> str:
        cache_key = self.cache.generate_key(profile_string, user_input)

        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f"决策缓存命中: {cache_key}")
            return cached

        full_prompt = planner_prompt_template.format(
            profile_string=profile_string,
            user_input=user_input,
        )

        try:
            logger.info(f"执行决策LLM调用: {cache_key}")
            response = self.model.invoke(full_prompt)
            result = response.content if hasattr(response, "content") else str(response)
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"决策引擎故障: {e}")
            return "[ANSWER]"
