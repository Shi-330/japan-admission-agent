# agent/memory.py (新建) -> 解耦streamlit 与 agent 的关系
import hashlib
from collections import OrderedDict
from typing import Optional, Any

class DecisionCache:
    """
    自给自足的缓存管理类，不依赖任何 UI 框架。
    使用 LRU (Least Recently Used) 策略防止内存溢出。
    """
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.data: OrderedDict[str, Any] = OrderedDict()  # 实现 LRU (最近最少使用) 策略

    def generate_key(self, profile_str: str, user_input: str) -> str:
        # 把原本在 ReactAgent 里的哈希逻辑挪到这里，实现内聚
        combined = f"{str(profile_str).strip()}|{str(user_input).strip()}".lower()
        return hashlib.md5(combined.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        if key in self.data:
            self.data.move_to_end(key) # 活跃数据移到末尾
            return self.data[key]
        return None

    def set(self, key: str, value: Any):
        if key in self.data:
            self.data.move_to_end(key)
        self.data[key] = value
        if len(self.data) > self.max_size:
            self.data.popitem(last=False) # 剔除最久没用的数据