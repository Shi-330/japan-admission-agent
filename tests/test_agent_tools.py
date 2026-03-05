import pytest
from pydantic import ValidationError
from agent.tools.agent_tools import (
    rag_fetch_context,
    RagFetchContextInput,
    web_search_tool,
    WebSearchInput,
    update_report_suggestions,
    UpdateReportSuggestionsInput
)

# 1. 测试基于 Pydantic 的 Schema 验证 (这非常关键，它是防止大模型幻觉掉进核心业务的第一道防线)

def test_web_search_schema_validation():
    """测试如果大模型没有传入必填字段 query，Schema 会自动拦截并报错"""
    with pytest.raises(ValidationError):
        # 缺少 query 参数，必须引发 Pydantic 的 ValidationError
        WebSearchInput()

def test_update_report_suggestions_schema_validation():
    """测试更新建议工具的入参合法性"""
    # 正常入参
    valid_input = UpdateReportSuggestionsInput(user_id="123", new_suggestions="考满分")
    assert valid_input.user_id == "123"

    # 如果模型只传了建议没传是谁的，必须拦截
    with pytest.raises(ValidationError):
        UpdateReportSuggestionsInput(new_suggestions="考满分")

# 2. 测试工具内部逻辑 (通过 Mock 隔离外部 API)

def test_web_search_tool_success(mocker):
    """测试外网搜索正常调用逻辑"""
    # 劫持 DDGS 的 invoke 方法
    mock_ddgs = mocker.patch("langchain_community.tools.DuckDuckGoSearchResults.invoke")
    mock_ddgs.return_value = "这是关于青木教授在东京大学的最新检索结果"
    
    result = web_search_tool.invoke({"query": "青木 东京大学 地震"})
    assert "关于青木教授" in result
    mock_ddgs.assert_called_once()

def test_web_search_tool_exception(mocker):
    """测试外网搜索崩溃时的优雅降级"""
    mock_ddgs = mocker.patch("langchain_community.tools.DuckDuckGoSearchResults.invoke")
    mock_ddgs.side_effect = Exception("Network Timeout Error") # 模拟拔网线
    
    # 工具不能直接崩溃抛错，必须返回给大模型包含 "失败" 的自解释信息，让模型自己换路
    result = web_search_tool.invoke({"query": "触发异常测试"})
    assert "外网检索失败" in result
    assert "Network Timeout Error" in result

def test_update_report_suggestions_success(mocker, mock_supabase_client):
    """测试核心业务动作：大模型修改看板建议"""
    # 控制 get_supabase() 返回我们的假 Client
    mocker.patch("agent.tools.agent_tools.get_supabase", return_value=mock_supabase_client)
    
    # 配置连续 Mock 链 table().update().eq().execute()
    mock_execute = mock_supabase_client.table().update().eq().execute
    mock_execute.return_value = {"status": 200}
    
    # 假装大模型调用了工具
    result = update_report_suggestions.invoke({
        "user_id": "test-uuid-001", 
        "new_suggestions": "冲刺早稻田"
    })
    
    # 断言：第一，返回值必须是友好的字符串告诉模型成功了
    assert "已成功更新" in result
    
    # 断言：第二，底层的 SQL 更新动作确实被触发了，并且带上了 REFINED 状态
    mock_supabase_client.table.assert_called_with("user_profiles")
    mock_supabase_client.table().update.assert_called_with({
        "suggestions": "冲刺早稻田",
        "report_status": "REFINED"
    })
    mock_supabase_client.table().update().eq.assert_called_with("id", "test-uuid-001")
