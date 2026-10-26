"""Matrix and benchmark tests for seniority status, score breakdown, and overall score calculation."""
import pytest
from unittest.mock import AsyncMock, patch
from app.utils.seniority_calculator import calculate_seniority_score_and_gap
from app.utils.score_calculator import calculate_overall_score
from app.utils.experience_extractor import ExperienceResult
from app.ai.orchestrator import DeterministicOrchestrator

MATRIX_CASES = [
    # Candidate Found
    ("found", 5, "found", 3, "match", 100, True),
    ("found", 3, "found", 4, "minor_gap", 80, True),
    ("found", 2, "found", 5, "significant_gap", 40, True),
    ("found", 5, "explicit_zero", 0, "match", 100, True),
    ("found", 5, "not_specified", None, "not_specified", None, False),
    ("found", 5, "error", None, "not_specified", None, False),

    # Candidate Explicit Zero
    ("explicit_zero", 0, "found", 3, "significant_gap", 40, True),
    ("explicit_zero", 0, "found", 1, "minor_gap", 80, True),
    ("explicit_zero", 0, "explicit_zero", 0, "match", 100, True),
    ("explicit_zero", 0, "not_specified", None, "not_specified", None, False),
    ("explicit_zero", 0, "error", None, "not_specified", None, False),

    # Candidate Not Found
    ("not_found", None, "found", 3, "unconfirmed", None, False),
    ("not_found", None, "explicit_zero", 0, "unconfirmed", None, False),
    ("not_found", None, "not_specified", None, "not_specified", None, False),
    ("not_found", None, "error", None, "not_specified", None, False),

    # Candidate Error
    ("error", None, "found", 3, "unconfirmed", None, False),
    ("error", None, "explicit_zero", 0, "unconfirmed", None, False),
    ("error", None, "not_specified", None, "not_specified", None, False),
    ("error", None, "error", None, "not_specified", None, False),
]

@pytest.mark.parametrize(
    "cand_status,cand_years,jd_status,jd_years,expected_status,expected_match,expected_assessed",
    MATRIX_CASES
)
def test_seniority_matrix_unit(
    cand_status, cand_years, jd_status, jd_years, expected_status, expected_match, expected_assessed
):
    cand_res = ExperienceResult(status=cand_status, years=cand_years, source="regex")
    jd_res = ExperienceResult(status=jd_status, years=jd_years, source="regex")

    result = calculate_seniority_score_and_gap(cand_res, jd_res)

    assert result["status"] == expected_status
    assert result["seniority_status"] == expected_status
    assert result["seniority_assessed"] == expected_assessed
    assert result["seniority_match"] == expected_match
    assert result["seniority_score"] == expected_match

    # Overall score calculation: skills = 50
    skills_score = 50
    overall = calculate_overall_score(skills_score, result["seniority_score"])
    if expected_match is None:
        # Renormalized to skills only
        assert overall == skills_score
    else:
        expected_overall = int(skills_score * 0.6 + expected_match * 0.4)
        assert overall == expected_overall


@pytest.fixture
def mock_external_orchestrator(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "cache_enabled", False)
    monkeypatch.setattr(
        "app.ai.client.GenAIClient.generate_structured_content",
        AsyncMock(return_value={
            "summary": "Strong alignment.",
            "keywords": ["Python"],
            "phrasing": [],
            "formatting_tips": [],
            "alignment_summary": "Meets requirements",
            "advice": "Good fit",
            "status": "not_found",
            "years": None,
            "evidence_quote": None
        })
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
async def test_benchmark_tech_senior_case(mock_external_orchestrator):
    """Tech senior case: candidate 6 years, JD 5 years -> match, seniority_match=100, overall=100."""
    orchestrator = DeterministicOrchestrator()
    request_data = {
        "resume": "Senior Software Engineer with 6 years of experience in Python, FastAPI, Docker, and PostgreSQL.",
        "jd_text": "Looking for a Senior Backend Engineer. Minimum 5 years of experience in Python, FastAPI, Docker, and PostgreSQL."
    }
    result = await orchestrator.process(request_data)
    assert result["seniority_status"] == "match"
    assert result["seniority_assessed"] is True
    assert result["score_breakdown"]["seniority_match"] == 100
    assert result["score_breakdown"]["skills_match"] == 100
    assert result["overall_score"] == 100


@pytest.mark.asyncio
async def test_benchmark_nursing_unparseable_jd_case(mock_external_orchestrator):
    """Nursing case: no recognized tech skills in JD -> unparseable_jd, all breakdown fields None."""
    orchestrator = DeterministicOrchestrator()
    request_data = {
        "resume": "Registered Nurse with 10 years of nursing experience in clinical triage and patient care.",
        "jd_text": "Staff Nurse needed with 5 years experience in clinical triage and patient care."
    }
    result = await orchestrator.process(request_data)
    assert result["status"] == "unparseable_jd"
    assert result["overall_score"] is None
    assert result["score_breakdown"]["skills_match"] is None
    assert result["score_breakdown"]["seniority_match"] is None
    assert result["score_breakdown"]["domain_match"] is None


@pytest.mark.asyncio
async def test_benchmark_low_evidence_case(mock_external_orchestrator):
    """Low evidence case: fewer skills than threshold -> low_confidence=True, overall calculated."""
    orchestrator = DeterministicOrchestrator()
    request_data = {
        "resume": "Software engineer with 4 years experience in Python building services.",
        "jd_text": "Looking for a Software engineer with 4 years experience in Python."
    }
    result = await orchestrator.process(request_data)
    assert result["low_confidence"] is True
    assert result["seniority_assessed"] is True
    assert result["score_breakdown"]["seniority_match"] == 100
    assert result["score_breakdown"]["skills_match"] == 100
    assert result["overall_score"] == 100


@pytest.mark.asyncio
async def test_benchmark_date_range_only_case(mock_external_orchestrator):
    """
    Date-range-only case:
    Candidate has date ranges only (2018 - 2024), no explicit years -> candidate not_found (unconfirmed).
    Candidate matches 2 out of 4 skills (50%).
    JD requires 5 years with Python, SQL, Docker, Kubernetes.
    Seniority must be unconfirmed and skipped, overall score must be 50 (skills only, NOT 46).
    """
    orchestrator = DeterministicOrchestrator()
    request_data = {
        "resume": "Software Engineer.\nEXPERIENCE\n2018 - 2024 Acme Corp.\nBuilt microservices in Python and SQL.",
        "jd_text": "Senior Engineer. Minimum 5 years experience with Python, SQL, Docker, and Kubernetes required."
    }
    result = await orchestrator.process(request_data)
    assert result["seniority_status"] == "unconfirmed"
    assert result["seniority_assessed"] is False
    assert result["score_breakdown"]["seniority_match"] is None
    assert result["score_breakdown"]["skills_match"] == 50
    # Must give exactly skills-only score: 50, NOT 46
    assert result["overall_score"] == 50
