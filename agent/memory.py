# agent/memory.py (新建) -> 解耦streamlit 与 agent 的关系
import hashlib
import time
from collections import OrderedDict
from typing import Optional, Any

class DecisionCache:
    """
    自给自足的缓存管理类，不依赖任何 UI 框架。
    使用 LRU (Least Recently Used) 策略 + TTL 过期机制防止内存溢出和决策过期。
    """
    def __init__(self, max_size: int = 100, ttl_seconds: int = 1800):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds  # 默认30分钟过期
        self.data: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def generate_key(self, profile_str: str, user_input: str) -> str:
        combined = f"{str(profile_str).strip()}|{str(user_input).strip()}".lower()
        return hashlib.md5(combined.encode()).hexdigest()

    def _is_expired(self, timestamp: float) -> bool:
        return (time.time() - timestamp) > self.ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self.data:
            value, ts = self.data[key]
            if self._is_expired(ts):
                del self.data[key]
                return None
            self.data.move_to_end(key)
            return value
        return None

    def set(self, key: str, value: Any):
        if key in self.data:
            self.data.move_to_end(key)
        self.data[key] = (value, time.time())
        if len(self.data) > self.max_size:
            self.data.popitem(last=False)

    def invalidate(self, key: str = None):
        """清除特定 key 或全部缓存"""
        if key:
            self.data.pop(key, None)
        else:
            self.data.clear()