import pytest
from unittest.mock import MagicMock
import os

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    强制拦截真实的环境变量，防止在运行单元测试时意外链接到真实的 Supabase 数据库
    或产生真实的 OpenAI 调用扣费。所有的测试用例自动套用。
    """
    monkeypatch.setenv("SUPABASE_URL", "https://mock-supabase-url.co")
    monkeypatch.setenv("SUPABASE_KEY", "mock-supabase-key")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "mock-dashscope-key")

@pytest.fixture
def mock_supabase_client(mocker):
    """
    提供一个全局模拟的 Supabase Client。
    """
    mock_client = MagicMock()
    # 比如当你想要模拟从 get_supabase() 返回时：
    # mocker.patch('agent.tools.agent_tools.get_supabase', return_value=mock_client)
    return mock_client
