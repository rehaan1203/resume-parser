"""Hermetic tests for experience extraction hotfix preventing calendar years and false positives."""
import pytest
from unittest.mock import AsyncMock, patch
from app.utils.experience_extractor import extract_years_experience
from app.ai.orchestrator import DeterministicOrchestrator

@pytest.fixture(autouse=True)
def mock_external_calls(monkeypatch):
    """Ensure LLM fallback returns 0 if reached during these tests."""
    from app.config import settings
    monkeypatch.setattr(settings, "cache_enabled", False)
    monkeypatch.setattr(
        "app.ai.client.GenAIClient.generate_structured_content",
        AsyncMock(return_value={"years": 0})
    )
    monkeypatch.setattr(
        "app.ai.client.GenAIClient.generate_content",
        AsyncMock(return_value="{}")
    )
    monkeypatch.setattr(
        "app.utils.link_processor.LinkProcessor.process_response",
        AsyncMock(side_effect=lambda resp: resp)
    )
    with patch("app.ai.orchestrator.asyncio.sleep", new_callable=AsyncMock):
        yield

@pytest.mark.asyncio
async def test_experience_header_with_calendar_year_not_extracted():
    """EXPERIENCE followed by a calendar year must not be parsed as 2019 years."""
    result = await extract_years_experience("EXPERIENCE\n2019 - Present Acme Corp")
    assert result != 2019
    assert result == 0  # LLM fallback returns 0 when regex finds nothing

@pytest.mark.asyncio
async def test_experience_colon_date_range_not_extracted():
    """Experience: 2018 - 2023 must not be parsed as 2018 years."""
    result = await extract_years_experience("Experience: 2018 - 2023")
    assert result != 2018
    assert result == 0

@pytest.mark.asyncio
async def test_graduated_years_ago_not_extracted():
    """Graduated 5 years ago must not be parsed as 5 years of experience."""
    result = await extract_years_experience("graduated 5 years ago")
    assert result != 5
    assert result == 0

@pytest.mark.asyncio
async def test_years_old_not_extracted():
    """5 years old must not be parsed as 5 years of experience."""
    result = await extract_years_experience("5 years old")
    assert result != 5
    assert result == 0

@pytest.mark.asyncio
async def test_valid_experience_control():
    """6 years of experience must be parsed as 6 years."""
    result = await extract_years_experience("Software Engineer with 6 years of experience in Python.")
    assert result == 6

@pytest.mark.asyncio
async def test_orchestrator_seniority_not_inflated_by_calendar_year():
    """Orchestrator run with a resume starting with calendar years must not map to Executive."""
    orchestrator = DeterministicOrchestrator()
    request_data = {
        "resume": "EXPERIENCE\n2019 - Present Acme Corp. Software engineer working on Python services.",
        "jd_text": "Looking for a Software engineer with 4 years experience in Python, SQL, and Docker."
    }
    result = await orchestrator.process(request_data)
    seniority = result["seniority_analysis"]
    
    # Seniority must NOT be 2019 years or Executive
    assert seniority["years_experience"] != 2019
    assert seniority["your_level"] != "Executive"
