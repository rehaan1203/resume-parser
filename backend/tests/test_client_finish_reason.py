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


@pytest.mark.asyncio
async def test_experience_extractor_truncation_fallback():
    """Test that extract_years_experience returns 0 on LLMTruncationError when regex fails."""
    from app.utils.experience_extractor import extract_years_experience
    with patch("app.utils.experience_extractor.GenAIClient") as MockClient, \
         patch("app.utils.experience_extractor.CacheManager.get", return_value=None):
        mock_client = MagicMock()
        mock_client.generate_structured_content = AsyncMock(
            side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
        )
        MockClient.return_value = mock_client
        # Text without numeric regex pattern triggers LLM fallback
        years = await extract_years_experience("Experienced developer lead on various systems")
        assert years == 0


@pytest.mark.asyncio
async def test_ats_optimizer_truncation_fallback():
    """Test that ATSOptimizer returns default suggestions on LLMTruncationError."""
    from app.ai.ats_optimizer import ATSOptimizer
    mock_client = MagicMock()
    mock_client.generate_structured_content = AsyncMock(
        side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
    )
    optimizer = ATSOptimizer(mock_client)
    result = await optimizer.optimize("resume", "jd", [])
    assert "keywords_to_add" in result
    assert "Python" in result["keywords_to_add"]


@pytest.mark.asyncio
async def test_interview_questions_truncation_fallback():
    """Test that InterviewQuestionGenerator returns default questions on LLMTruncationError."""
    from app.ai.interview_questions import InterviewQuestionGenerator
    mock_client = MagicMock()
    mock_client.generate_structured_content = AsyncMock(
        side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
    )
    generator = InterviewQuestionGenerator(mock_client)
    questions = await generator.generate_questions("resume", "jd", ["Kubernetes"], ["Python"])
    assert len(questions) > 0
    assert "Kubernetes" in questions[0]["question"]


@pytest.mark.asyncio
async def test_career_advisor_truncation_fallback():
    """Test that CareerAdvisor returns default advice on LLMTruncationError."""
    from app.ai.career_advisor import CareerAdvisor
    mock_client = MagicMock()
    mock_client.generate_structured_content = AsyncMock(
        side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
    )
    advisor = CareerAdvisor(mock_client)
    advice = await advisor.get_advice("resume", "5 years", "Principal Engineer", ["Go"])
    assert "short_term_goals" in advice
    assert any("Go" in goal for goal in advice["short_term_goals"])


@pytest.mark.asyncio
async def test_legacy_llm_truncation_fallback():
    """Test that LLMService methods in llm.py handle LLMTruncationError without raising."""
    from app.ai.llm import LLMService
    mock_client = MagicMock()
    mock_client.generate_structured_content = AsyncMock(
        side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
    )
    service = LLMService(mock_client)
    
    friction = await service.analyze_friction("resume", "jd", [])
    assert "skill_gaps" in friction
    
    roadmap = await service.generate_roadmap(["Python"], ["SQL"])
    assert roadmap == []
    
    analysis = await service.generate_analysis("resume", "jd")
    assert analysis["overall_score"] == 72


@pytest.mark.asyncio
async def test_transition_route_truncation_fallback():
    """Test that transition route functions return structured fallbacks on LLMTruncationError."""
    from app.api.routes.transition import generate_transition_roadmap, generate_transition_tips
    with patch("app.api.routes.transition.GenAIClient") as MockClient:
        mock_client = MagicMock()
        mock_client.generate_structured_content = AsyncMock(
            side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
        )
        MockClient.return_value = mock_client
        
        roadmap = await generate_transition_roadmap("software", "legal", "resume...", "jd...")
        assert roadmap["type"] == "career_change"
        assert len(roadmap["phases"]) == 1
        
        tips = await generate_transition_tips("software", "legal", "resume...", "jd...")
        assert "resume_strategy" in tips
        assert len(tips["resume_strategy"]) >= 1


@pytest.mark.asyncio
async def test_orchestrator_resilience_to_llm_truncation():
    """Test that DeterministicOrchestrator pipeline succeeds even when Phase 3 LLM calls are truncated."""
    from app.ai.orchestrator import DeterministicOrchestrator
    with patch("app.ai.explainer.GenAIClient") as MockExplainerClient:
        mock_client = MagicMock()
        mock_client.generate_structured_content = AsyncMock(
            side_effect=LLMTruncationError("Truncated", completion_tokens=4000)
        )
        MockExplainerClient.return_value = mock_client

        orchestrator = DeterministicOrchestrator()
        result = await orchestrator.process({
            "resume": "Experienced Python, Docker, Kubernetes and AWS cloud engineer with 5 years experience.",
            "jd_text": "Senior Python, Docker, Kubernetes and AWS cloud engineer with 5+ years experience required."
        })
        assert result.get("overall_score") is not None
        assert "executive_summary" in result
        assert "Candidate achieved a" in result["executive_summary"]

