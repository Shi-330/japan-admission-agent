import pytest
from fastapi.testclient import TestClient
from backend.api.server import app
from user.profile_manager import UserProfile
from unittest.mock import MagicMock, patch

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@patch("backend.api.server.HeadlessAgent")
def test_chat_endpoint(mock_headless_agent):
    # Mock the HeadlessAgent to return a generator with status markers
    mock_agent_instance = mock_headless_agent.return_value
    mock_agent_instance.chat_stream.return_value = [
        "[STATUS:UNDERSTANDING]", 
        "[STATUS:GENERATING]",
        "Hello", " world", "!"
    ]

    # Define a test profile
    test_profile = UserProfile(
        jlpt_level="N1",
        eju_score=700,
        gpa=3.8,
        target_major="CS",
        undergraduate_school="Tsinghua",
        english_score="100"
    )

    # Request body
    payload = {
        "query": "hello",
        "user_profile": test_profile.model_dump()
    }

    # Use client.post with json payload
    response = client.post("/v1/chat", json=payload)
    
    assert response.status_code == 200
    assert "[STATUS:UNDERSTANDING]" in response.text
    assert "[STATUS:GENERATING]" in response.text
    assert "Hello world!" in response.text
    mock_headless_agent.assert_called_once()
