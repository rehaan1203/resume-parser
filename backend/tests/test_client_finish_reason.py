"""Tests for LLM finish_reason checking, token usage logging, and LLMTruncationError."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.client import GenAIClient
from app.utils.exceptions import LLMTruncationError
from app.ai.explainer import Phase3Explainer

def make_mock_chat_response(content: str, finish_reason: str = "stop", completion_tokens: int = 150):
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = finish_reason
    response.choices = [choice]
    response.usage = MagicMock()
    response.usage.completion_tokens = completion_tokens
    return response

@pytest.mark.asyncio
async def test_generate_content_normal_finish_reason():
    """Test that normal completion with finish_reason='stop' returns content cleanly."""
    with patch("app.ai.client.settings") as mock_settings:
        mock_settings.mistral_api_key = "test_key"
        mock_settings.ai_max_retries = 1
        mock_settings.ai_timeout_seconds = 10
        mock_settings.ai_model = "mistral-small-latest"

        client = GenAIClient()
        client.client = MagicMock()
        mock_resp = make_mock_chat_response("Valid completion response", finish_reason="stop", completion_tokens=42)
        client.client.chat = AsyncMock(return_value=mock_resp)

        result = await client.generate_content("Hello prompt")
        assert result == "Valid completion response"

@pytest.mark.asyncio
async def test_generate_content_truncated_raises_llm_truncation_error():
    """Test that finish_reason='length' raises LLMTruncationError with completion_tokens."""
    with patch("app.ai.client.settings") as mock_settings:
        mock_settings.mistral_api_key = "test_key"
        mock_settings.ai_max_retries = 1
        mock_settings.ai_timeout_seconds = 10
        mock_settings.ai_model = "mistral-small-latest"

        client = GenAIClient()
        client.client = MagicMock()
        mock_resp = make_mock_chat_response("Incomplete text...", finish_reason="length", completion_tokens=8192)
        client.client.chat = AsyncMock(return_value=mock_resp)

        with pytest.raises(LLMTruncationError) as exc_info:
            await client.generate_content("Long prompt")

        assert "truncated due to length limit" in str(exc_info.value)
        assert exc_info.value.completion_tokens == 8192

@pytest.mark.asyncio
async def test_caller_fallback_on_truncation():
    """Test that Phase3Explainer callers handle LLMTruncationError gracefully via fallbacks."""
    with patch("app.ai.explainer.GenAIClient") as MockGenAIClient:
        mock_client = MagicMock()
        # Mock structured content generation to raise LLMTruncationError
        mock_client.generate_structured_content = AsyncMock(
            side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
        )
        MockGenAIClient.return_value = mock_client

        explainer = Phase3Explainer()
        summary = await explainer.generate_executive_summary(
            score=85,
            strengths=["Python", "SQL"],
            gaps=["Docker"],
            seniority_gap=0
        )
        assert "Candidate achieved a 85% match" in summary
        assert "Python" in summary
