"""Tests for LLM experience extraction fallback with schema and evidence quote verification."""
import pytest
from unittest.mock import AsyncMock
from app.utils.exceptions import LLMTruncationError
from app.utils.experience_extractor import (
    extract_candidate_experience_with_llm,
    extract_required_experience_with_llm,
    verify_evidence_quote,
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


# --- Adversarial Mocked-LLM Tests for verify_evidence_quote ---

@pytest.mark.asyncio
async def test_candidate_llm_adversarial_graduated_ago():
    """Adversarial LLM quote 'graduated 5 years ago' with years 5 is rejected and downgrades to not_found."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 5,
        "evidence_quote": "graduated 5 years ago"
    }
    resume_text = "Software engineer who graduated 5 years ago with computer science degree."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_candidate_llm_adversarial_skill_duration():
    """Adversarial LLM quote 'Python for 3 years' with years 3 is rejected and downgrades to not_found."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 3,
        "evidence_quote": "Python for 3 years"
    }
    resume_text = "Backend engineer writing Python for 3 years building web applications."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_candidate_llm_adversarial_quote_not_in_text():
    """Adversarial LLM quote that does not appear in the resume text is rejected."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 8,
        "evidence_quote": "8 years of total experience leading teams"
    }
    resume_text = "Full stack developer proficient in React, Node, and Postgres."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_candidate_llm_number_word_ten_years():
    """LLM quote containing number word 'ten years' verifies against integer years 10."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 10,
        "evidence_quote": "a career spanning ten years"
    }
    resume_text = "Staff product manager possessing a career spanning ten years leading enterprise systems."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "found"
    assert res.years == 10
    assert res.source == "llm"
    assert res.evidence == "a career spanning ten years"


@pytest.mark.asyncio
async def test_candidate_llm_number_word_a_decade():
    """LLM quote containing 'a decade' verifies against integer years 10."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 10,
        "evidence_quote": "a career spanning a decade"
    }
    resume_text = "Staff product manager possessing a career spanning a decade leading enterprise systems."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "found"
    assert res.years == 10
    assert res.source == "llm"
    assert res.evidence == "a career spanning a decade"


@pytest.mark.asyncio
async def test_candidate_llm_adversarial_explicit_zero_not_whole_career():
    """Adversarial LLM explicit_zero quote that is NOT a whole-career statement is rejected."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "explicit_zero",
        "years": 0,
        "evidence_quote": "no experience with Kubernetes"
    }
    resume_text = "Senior developer with extensive backend skills and no experience with Kubernetes."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.parametrize("quote,source,years,expected_valid", [
    ("graduated 5 years ago", "Software engineer who graduated 5 years ago.", 5, False),
    ("Python for 3 years", "Developer writing Python for 3 years.", 3, False),
    ("8 years of total experience", "Completely different text without the quote.", 8, False),
    ("ten years of experience", "Leader with ten years of experience.", 10, True),
    ("a decade of experience", "Leader with a decade of experience.", 10, True),
    ("no experience with Kubernetes", "Engineer with no experience with Kubernetes.", 0, False),
    ("no prior work experience", "Graduate with no prior work experience.", 0, True),
    ("55 years of experience", "Veteran with 55 years of experience.", 55, False),
    ("experience since 2018", "Developer with experience since 2018.", 2018, False),
])
def test_verify_evidence_quote_adversarial_matrix(quote, source, years, expected_valid):
    """Directly assert evidence quote verification across adversarial filters and valid cases."""
    assert verify_evidence_quote(quote, source, years) is expected_valid


