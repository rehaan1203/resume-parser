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
        "evidence_quote": "over seven years working in software",
        "scope": "total_career",
        "covers_entire_career": True
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
        "evidence_quote": "10 years of experience at Google",
        "scope": "total_career"
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
        "evidence_quote": "no prior professional experience",
        "scope": "total_career"
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
        "evidence_quote": "graduated 5 years ago",
        "scope": "other"
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
        "evidence_quote": "Python for 3 years",
        "scope": "skill_or_tool"
    }
    resume_text = "Backend engineer writing Python for 3 years building web applications."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_candidate_llm_scope_not_total_career_rejected():
    """Valid quote with non-total_career scope (e.g. skill_or_tool) is rejected and downgrades to not_found."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 5,
        "evidence_quote": "5 years in FastAPI",
        "scope": "skill_or_tool"
    }
    resume_text = "Built high-performance microservices with 5 years in FastAPI and Python."
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
        "evidence_quote": "8 years of total experience leading teams",
        "scope": "total_career"
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
        "evidence_quote": "a career spanning ten years",
        "scope": "total_career",
        "covers_entire_career": True
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
        "evidence_quote": "a career spanning a decade",
        "scope": "total_career",
        "covers_entire_career": True
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
        "evidence_quote": "no experience with Kubernetes",
        "scope": "skill_or_tool"
    }
    resume_text = "Senior developer with extensive backend skills and no experience with Kubernetes."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_candidate_llm_seeking_entry_level_gives_not_found():
    """Resume LLM returning explicit_zero with 'seeking entry-level roles' must NOT verify as zero and gives not_found."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "explicit_zero",
        "years": 0,
        "evidence_quote": "seeking entry-level roles",
        "scope": "other"
    }
    resume_text = "Computer science graduate seeking entry-level roles in backend development."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_jd_llm_entry_level_position_gives_explicit_zero():
    """JD LLM returning explicit_zero with 'entry-level position' verifies and gives explicit_zero."""
    from unittest.mock import patch
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "explicit_zero",
        "years": 0,
        "evidence_quote": "entry-level position"
    }
    jd_text = "Looking for a motivated junior developer for this entry-level position."
    with patch("app.utils.experience_extractor.extract_required_experience", return_value=ExperienceResult(status="not_specified", years=None, source="regex")):
        res = await extract_required_experience_with_llm(jd_text, client=mock_client)
    assert res.status == "explicit_zero"
    assert res.years == 0
    assert res.evidence == "entry-level position"
    assert res.source == "llm"


ADVERSARIAL_QUOTES_MATRIX = [
    ("graduated 5 years ago", "Candidate graduated 5 years ago from university", 5, "candidate", "other", False),
    ("35 years of age", "Candidate is 35 years of age", 35, "candidate", "other", False),
    ("28 years old", "Senior developer, 28 years old", 28, "candidate", "other", False),
    ("Python for 3 years", "Used Python for 3 years building APIs", 3, "candidate", "skill_or_tool", False),
    ("5 years in FastAPI", "Built backends with 5 years in FastAPI", 5, "candidate", "skill_or_tool", False),
    ("6 years of Terraform", "Infrastructure management with 6 years of Terraform", 6, "candidate", "skill_or_tool", False),
    ("6 years of Excel", "Financial modeling with 6 years of Excel", 6, "candidate", "skill_or_tool", False),
    ("4 years with Kubernetes", "Container orchestration with 4 years with Kubernetes", 4, "candidate", "skill_or_tool", False),
    ("3 years using React", "Frontend UI with 3 years using React", 3, "candidate", "skill_or_tool", False),
    ("4 years in college", "Completed 4 years in college studying CS", 4, "candidate", "education", False),
    ("4 years of university", "Spent 4 years of university in engineering", 4, "candidate", "education", False),
    ("3 years of study", "After 3 years of study in physics", 3, "candidate", "education", False),
    ("seeking entry-level roles", "Graduate seeking entry-level roles", 0, "candidate", "other", False),
    ("recent graduate with 0 years", "A recent graduate with 0 years on the job", 0, "candidate", "other", False),
    ("0-2 years required", "Requires 0-2 years experience", 0, "candidate", "other", False),
]

GENUINE_QUOTES_MATRIX = [
    ("8 years of professional experience", "Senior dev with 8 years of professional experience", 8, "candidate", "total_career", True),
    ("10 years of nursing experience", "RN with 10 years of nursing experience in ICU", 10, "candidate", "total_career", True),
    ("10+ years in nursing", "RN with 10+ years in nursing across critical care", 10, "candidate", "total_career", True),
    ("A decade in medicine", "Physician with A decade in medicine and clinical practice", 10, "candidate", "total_career", True),
    ("12 years of legal practice", "Attorney with 12 years of legal practice", 12, "candidate", "total_career", True),
    ("6 years in the teaching profession", "Educator with 6 years in the teaching profession", 6, "candidate", "total_career", True),
    ("7 years in sales", "Account executive with 7 years in sales closing enterprise deals", 7, "candidate", "total_career", True),
    ("15 years of industry experience", "Manager with 15 years of industry experience", 15, "candidate", "total_career", True),
    ("7 years of clinical experience", "Physician with 7 years of clinical experience", 7, "candidate", "total_career", True),
    ("8 years as an accountant", "CPA with 8 years as an accountant", 8, "candidate", "total_career", True),
    ("a decade of experience in corporate finance", "Analyst with a decade of experience in corporate finance", 10, "candidate", "total_career", True),
    ("over 5 years of work experience in carpentry", "Carpenter with over 5 years of work experience in carpentry", 5, "candidate", "total_career", True),
    ("14 years in the culinary industry", "Executive Chef with 14 years in the culinary industry", 14, "candidate", "total_career", True),
    ("two decades of career experience in architecture", "Lead Architect with two decades of career experience in architecture", 20, "candidate", "total_career", True),
    ("3 years of experience as a dental hygienist", "Clinician with 3 years of experience as a dental hygienist", 3, "candidate", "total_career", True),
    ("9 years of experience in supply chain", "Logistics specialist with 9 years of experience in supply chain", 9, "candidate", "total_career", True),
    ("0 years of experience", "Junior applicant with 0 years of experience", 0, "candidate", "total_career", True),
    ("no prior work experience", "First-time job seeker with no prior work experience", 0, "candidate", "total_career", True),
]

@pytest.mark.parametrize("quote,source,years,mode,scope,expected_valid", ADVERSARIAL_QUOTES_MATRIX + GENUINE_QUOTES_MATRIX)
def test_verify_evidence_quote_comprehensive_matrix(quote, source, years, mode, scope, expected_valid):
    """Directly assert evidence quote verification across adversarial and genuine profession quotes with scope."""
    assert verify_evidence_quote(quote, source, years, mode=mode, scope=scope) is expected_valid


TEACHING_PHRASES = [
    ("15 years in education", "Candidate with 15 years in education leading curriculum design.", 15),
    ("10 years in school administration", "Educator with 10 years in school administration.", 10),
    ("8 years teaching high school mathematics", "Teacher with 8 years teaching high school mathematics.", 8),
    ("12 years in secondary education", "Leader with 12 years in secondary education.", 12),
    ("5 years as an elementary school teacher", "Certified teacher with 5 years as an elementary school teacher.", 5),
    ("20 years in public education", "Veteran with 20 years in public education reform.", 20),
    ("6 years in higher education leadership", "Dean with 6 years in higher education leadership.", 6),
    ("14 years of classroom teaching experience", "Instructor with 14 years of classroom teaching experience.", 14),
    ("7 years as a school principal", "Administrator with 7 years as a school principal.", 7),
    ("11 years in educational counseling", "Counselor with 11 years in educational counseling.", 11),
]

@pytest.mark.parametrize("quote,text,years", TEACHING_PHRASES)
def test_teaching_phrases_accepted(quote, text, years):
    """Legitimate teaching and educational leadership phrases are accepted and not rejected by education filter."""
    assert verify_evidence_quote(quote, text, years, mode="candidate", scope="total_career") is True


@pytest.mark.asyncio
async def test_covers_entire_career_false_rejected():
    """LLM returning covers_entire_career=False downgrades to not_found even if scope is total_career."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 6,
        "evidence_quote": "6 years across engineering environments",
        "scope": "total_career",
        "covers_entire_career": False
    }
    resume_text = "Developer with 6 years across engineering environments at Acme."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None


@pytest.mark.asyncio
async def test_adversarial_student_researcher_rejected():
    """Adversarial quote '2 years as a student researcher' is rejected by student/intern filter."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content.return_value = {
        "status": "found",
        "years": 2,
        "evidence_quote": "2 years as a student researcher",
        "scope": "total_career",
        "covers_entire_career": True
    }
    resume_text = "Graduate assistant with 2 years as a student researcher in AI."
    res = await extract_candidate_experience_with_llm(resume_text, client=mock_client)
    assert res.status == "not_found"
    assert res.years is None




