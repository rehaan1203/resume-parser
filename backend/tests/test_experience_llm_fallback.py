"""Tests for LLM experience extraction fallback with schema and evidence quote verification."""
import pytest
from unittest.mock import AsyncMock
from app.utils.exceptions import LLMTruncationError
from app.utils.experience_extractor import (
    extract_candidate_experience_with_llm,
    extract_required_experience_with_llm,
    ExperienceResult
)

@pytest.mark.asyncio
async def test_candidate_llm_found_valid_quote():
    """Found status with valid quote verified in text returns found."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 7,
        "evidence_quote": "over seven years working in software"
    }
    resume_text = "Senior developer with over seven years working in software architecture and systems."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "found"
    assert res.years == 7
    assert res.evidence == "over seven years working in software"
    assert res.source == "llm"

@pytest.mark.asyncio
async def test_candidate_llm_found_invalid_quote_downgrades():
    """Found status with a fabricated quote not in the text downgrades to not_found."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 10,
        "evidence_quote": "10 years of experience at Google"
    }
    resume_text = "Senior developer who worked on various distributed backend projects."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None

@pytest.mark.asyncio
async def test_candidate_llm_explicit_zero():
    """Explicit zero with verified quote returns explicit_zero."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "explicit_zero",
        "years": 0,
        "evidence_quote": "no prior professional experience"
    }
    resume_text = "Computer science graduate with no prior professional experience seeking first role."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "explicit_zero"
    assert res.years == 0

@pytest.mark.asyncio
async def test_candidate_llm_not_found():
    """LLM returning not_found returns not_found with None years."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "not_found",
        "years": None,
        "evidence_quote": None
    }
    resume_text = "Developer specializing in React and Node."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None

@pytest.mark.asyncio
async def test_candidate_llm_truncation_gives_error():
    """LLMTruncationError results in status error."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.side_effect = LLMTruncationError("Response truncated")
    resume_text = "Developer with extensive background."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "error"
    assert res.years is None
    assert "Response truncated" in res.evidence

@pytest.mark.asyncio
async def test_candidate_llm_exception_gives_error():
    """Unexpected exception gives status error."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.side_effect = RuntimeError("API connection failure")
    resume_text = "Developer with extensive background."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "error"
    assert res.years is None
    assert "API connection failure" in res.evidence

@pytest.mark.asyncio
async def test_jd_llm_found_valid_quote():
    """JD LLM fallback finds minimum required experience."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 4,
        "evidence_quote": "candidates must possess 4 years in operations"
    }
    jd_text = "Hiring logistics lead: candidates must possess 4 years in operations management."
    res = await extract_required_experience_with_llm(jd_text, client=mock_client)
    assert res.status == "found"
    assert res.years == 4
    assert res.evidence == "candidates must possess 4 years in operations"

@pytest.mark.asyncio
async def test_jd_llm_invalid_quote_downgrades():
    """JD LLM fallback with quote missing from text downgrades to not_specified."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 5,
        "evidence_quote": "minimum 5 years"
    }
    jd_text = "Hiring software engineer with team collaboration skills."
    res = await extract_required_experience_with_llm(jd_text, client=mock_client)
    assert res.status == "not_specified"
    assert res.years is None
