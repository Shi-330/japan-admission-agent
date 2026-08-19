"""事实信号检测单测:无信号消息跳过事实抽取,有信号消息触发。"""
import pytest
from agent.orchestrator import has_fact_signal


@pytest.mark.parametrize("msg", [
    "谢谢", "好的", "嗯", "明白了", "然后呢", "帮我查一下京都大学", "东京有什么学校",
])
def test_no_fact_signal(msg):
    assert has_fact_signal(msg) is False


@pytest.mark.parametrize("msg", [
    "我N1 145分",
    "我在清华读计算机",
    "我的专业是自动化",
    "我GPA 3.2",
    "我做过NLP项目",
    "我打算去日本读研",
])
def test_has_fact_signal(msg):
    assert has_fact_signal(msg) is True


def test_empty_message():
    assert has_fact_signal("") is False
    assert has_fact_signal(None) is False
