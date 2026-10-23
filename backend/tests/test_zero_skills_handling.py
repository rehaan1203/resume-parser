"""Tests for zero-JD-skills handling, unparseable_jd status, and low_evidence flags."""
import pytest
from app.ai.orchestrator import DeterministicOrchestrator
from app.utils.score_calculator import calculate_skills_score, calculate_overall_score

@pytest.mark.asyncio
async def test_zero_jd_skills_returns_unparseable_jd():
    """Test that a JD with 0 detected skills returns unparseable_jd with overall_score null."""
    orchestrator = DeterministicOrchestrator()
    
    # Text with zero COMMON_SKILLS
    request_data = {
        "resume": "A seasoned specialist with 5 years experience in bespoke logistics, regional delivery, and scheduling.",
        "jd_text": "We are seeking a coordinator for logistics delivery and regional operations with 5 years experience."
    }
    
    result = await orchestrator.process(request_data)
    
    assert result["status"] == "unparseable_jd"
    assert result["overall_score"] is None
    assert result["skills_detected"] == 0
    assert result["low_confidence"] is True
    assert "We couldn't recognize specific requirements in this job description" in result["message"]
    # Verify NO fabricated skills in missing_skills
    assert result["skill_analysis"]["missing_skills"] == []
    assert result["skill_analysis"]["matching_skills"] == []
    assert result["skill_gaps"] == []

@pytest.mark.asyncio
async def test_low_evidence_flag_on_few_skills():
    """Test that JD with fewer than 3 skills triggers low_confidence=True without blocking analysis."""
    orchestrator = DeterministicOrchestrator()
    
    # Text with only 1 skill from COMMON_SKILLS (e.g. Python)
    request_data = {
        "resume": "Software developer with 3 years experience building apps in Python.",
        "jd_text": "Looking for a software developer with 3 years experience in Python."
    }
    
    result = await orchestrator.process(request_data)
    
    assert result.get("status") != "unparseable_jd"
    assert result["overall_score"] is not None
    assert result["skills_detected"] == 1
    assert result["low_confidence"] is True
    assert "Python" in result["skill_analysis"]["matching_skills"]

def test_score_calculator_zero_jd_skills():
    """Test that score_calculator returns 0 when total_jd_skills is 0."""
    assert calculate_skills_score(0, 0) == 0
    assert calculate_skills_score(2, 0) == 0
    assert calculate_skills_score(2, 4) == 50
