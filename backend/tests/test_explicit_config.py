import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.config import Settings
from app.ai.client import GenAIClient
from app.utils.logger import logger

def test_default_mistral_endpoint_and_model():
    """Default mistral_endpoint is api.mistral.ai and ai_model is mistral-small-latest."""
    s = Settings(
        _env_file=None,
        port=8000,
        cors_origins=["*"],
        mistral_api_key="mock-key",
        tools_enabled=False
    )
    assert s.mistral_endpoint == "https://api.mistral.ai"
    assert s.ai_model == "mistral-small-latest"

def test_gemini_model_raises_startup_error():
    """Specifying a gemini model raises a ValueError on startup."""
    with pytest.raises(ValueError, match="gemini AI_MODEL"):
        Settings(
            _env_file=None,
            port=8000,
            cors_origins=["*"],
            mistral_api_key="mock-key",
            ai_model="gemini-2.5-flash",
            tools_enabled=False
        )

def test_mstrl_key_with_non_codestral_endpoint_warns():
    """An mstrl_ key configured with a non-codestral endpoint emits a warning log."""
    messages = []
    sink_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
    try:
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.mistral_api_key = "mstrl_secret123"
            mock_settings.mistral_endpoint = "https://api.mistral.ai"
            mock_settings.ai_max_retries = 1
            mock_settings.ai_timeout_seconds = 5

            client = GenAIClient()
            assert client.endpoint == "https://api.mistral.ai"
            assert any("mstrl_ key detected with non-codestral endpoint" in m for m in messages)
    finally:
        logger.remove(sink_id)

@pytest.mark.asyncio
async def test_generate_content_logs_host_and_model_without_key():
    """generate_content logs the resolved host and model after resolution, never the key."""
    messages = []
    sink_id = logger.add(lambda msg: messages.append(str(msg)), level="INFO")
    try:
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.mistral_api_key = "test-key-do-not-log"
            mock_settings.mistral_endpoint = "https://api.mistral.ai"
            mock_settings.ai_model = "mistral-small-latest"
            mock_settings.ai_max_retries = 1
            mock_settings.ai_timeout_seconds = 5

            client = GenAIClient()
            mock_chat_resp = MagicMock()
            mock_chat_resp.model = "mistral-small-2409"
            mock_choice = MagicMock()
            mock_choice.message.content = "Response content"
            mock_choice.finish_reason = "stop"
            mock_chat_resp.choices = [mock_choice]
            mock_chat_resp.usage = MagicMock(completion_tokens=25)

            client.client.chat = AsyncMock(return_value=mock_chat_resp)

            res = await client.generate_content("Hello test")
            assert res == "Response content"
            # Verify host and model are logged
            assert any("Calling endpoint api.mistral.ai with model mistral-small-latest" in m for m in messages)
            assert any("Response received from model mistral-small-2409" in m for m in messages)
            # Verify key is never logged anywhere in output
            assert not any("test-key-do-not-log" in m for m in messages)
    finally:
        logger.remove(sink_id)
