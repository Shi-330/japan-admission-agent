import pytest
from user.profile_manager import UserProfile, ProfileManager
from unittest.mock import MagicMock

def test_user_profile_defaults():
    """测试画像默认值能否正常生成，防止缺少字段导致崩溃"""
    profile = UserProfile()
    assert profile.jlpt_level == "无"
    assert profile.eju_score == 0
    assert profile.gpa == 0.0
    assert profile.target_major == "未设定"
    assert profile.english_score == "未参加"
    assert profile.report_status == "NONE"
    assert profile.suggestions is None
    assert profile.report_content == {}

def test_user_profile_dump():
    """测试字典化功能，这是存入 Supabase 的关键步骤"""
    profile = UserProfile(jlpt_level="N1", gpa=3.8)
    data = profile.to_dict()
    assert data["jlpt_level"] == "N1"
    assert data["gpa"] == 3.8
    assert "report_status" in data

def test_profile_manager_get_profile_success(mocker, mock_supabase_client):
    """测试 ProfileManager 读取到数据库已有数据的情况"""
    mgr = ProfileManager()
    mgr.supabase = mock_supabase_client

    # 配置连串调用的 Mock 返回: table().select().eq().execute()
    mock_response = MagicMock()
    mock_response.data = [{
        "id": "123",
        "jlpt_level": "N2",
        "gpa": 3.5,
        "unexpected_field": "should_be_ignored" # 模拟数据库里有多余的垃圾字段
    }]
    mock_supabase_client.table().select().eq().execute.return_value = mock_response

    profile = mgr.get_profile("123")
    assert profile.jlpt_level == "N2"
    assert profile.gpa == 3.5
    assert not hasattr(profile, "unexpected_field") # Pydantic 的过滤能力

def test_profile_manager_get_profile_empty(mocker, mock_supabase_client):
    """测试数据库没查到或者异常时，返回纯净的默认实例"""
    mgr = ProfileManager()
    mgr.supabase = mock_supabase_client
    
    # 模拟没这人
    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase_client.table().select().eq().execute.return_value = mock_response

    profile = mgr.get_profile("404")
    assert profile.jlpt_level == "无" 
    
    # 模拟数据库彻底挂了抛异常
    mock_supabase_client.table().select().eq().execute.side_effect = Exception("DB Down")
    profile2 = mgr.get_profile("error_id")
    assert profile2.eju_score == 0
