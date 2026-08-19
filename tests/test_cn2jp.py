"""cn2jp 归一化缓存单测:同一 term 第二次不发 LLM,静态命中路径零 LLM。"""
import pytest
from utils.cn2jp import normalize, _llm_cache


class _FakeResp:
    def __init__(self, content: str):
        self.content = content


class _FakeModel:
    """记录 invoke 调用次数,返回固定的日文词表。"""

    def __init__(self):
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        return _FakeResp("量子情報学,量子計算")


def test_llm_fallback_is_cached_same_term():
    """同一 term 第二次调用不发 LLM(命中缓存)。"""
    _llm_cache.clear()
    model = _FakeModel()
    term = "冷门量子方向测试项"  # 不在静态映射中,触发 LLM 路径

    r1 = normalize(term, chat_model=model)
    r2 = normalize(term, chat_model=model)

    assert model.calls == 1  # 第二次命中缓存,不再 invoke
    assert r1 == r2
    assert term in r1            # 结果包含原词
    assert "量子情報学" in r1    # 结果包含 LLM 返回的日文词


def test_static_match_triggers_no_llm():
    """静态映射命中的 term 不发 LLM(即使传了 chat_model)。"""
    _llm_cache.clear()
    model = _FakeModel()
    terms = normalize("计算机", chat_model=model)

    assert model.calls == 0  # 静态命中,零 LLM
    assert "情報工学" in terms  # 静态映射的日文词
