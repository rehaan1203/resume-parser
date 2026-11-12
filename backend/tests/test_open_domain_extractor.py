"""Hermetic unit tests for D4 Open-Domain Requirement Extractor and Weighted Math."""
import pytest
from app.ai.open_domain_extractor import OpenDomainExtractor
from app.models.open_domain_models import RequirementCategory, ImportanceTier
from app.utils.score_calculator import calculate_open_domain_weighted_score

def test_remap_non_numeric_durations():
    extractor = OpenDomainExtractor()
    raw_reqs = [
        {"name": "5+ years in acute care", "category": "experience_duration", "raw_text": "5+ years in acute care"},
        {"name": "Clean driving record", "category": "experience_duration", "raw_text": "Must have clean driving record"},
        {"name": "Pass background check", "category": "experience_duration", "raw_text": "Subject to criminal background clearance"},
        {"name": "Valid state driver license", "category": "experience_duration", "raw_text": "Possess valid state license"}
    ]
    remapped = extractor.remap_non_numeric_durations(raw_reqs)
    # The first item has numeric duration, stays domain_experience
    assert remapped[0]["category"] == RequirementCategory.DOMAIN_EXPERIENCE.value
    # The others must be remapped to skill or credential
    assert remapped[1]["category"] in (RequirementCategory.SKILL.value, RequirementCategory.CREDENTIAL.value)
    assert remapped[2]["category"] in (RequirementCategory.SKILL.value, RequirementCategory.CREDENTIAL.value)
    assert remapped[3]["category"] == RequirementCategory.CREDENTIAL.value

def test_weighted_scoring_formula():
    requirements = [
        {"name": "Python", "category": "skill", "importance": "must_have"},       # w = 1.0
        {"name": "FastAPI", "category": "skill", "importance": "must_have"},      # w = 1.0
        {"name": "Docker", "category": "tool", "importance": "preferred"},        # w = 0.5
        {"name": "Kubernetes", "category": "tool", "importance": "bonus"}         # w = 0.25
    ]
    matches = [
        {"requirement_name": "Python", "credit": 1.0},
        {"requirement_name": "FastAPI", "credit": 0.5},
        {"requirement_name": "Docker", "credit": 1.0},
        {"requirement_name": "Kubernetes", "credit": 0.0}
    ]
    scoring = calculate_open_domain_weighted_score(requirements, matches)
    assert scoring["overall_score"] == 73
    assert 72.5 <= scoring["weighted_score"] <= 73.0
    assert scoring["total_weight"] == 2.75
    assert scoring["earned_weight"] == 2.0
    assert "skill" in scoring["category_breakdown"]
    assert "tool" in scoring["category_breakdown"]

@pytest.mark.asyncio
async def test_open_domain_evaluation_multidomain():
    extractor = OpenDomainExtractor()
    nursing_jd = """
    Registered Nurse - Telemetry / ICU
    Requirements:
    - Active RN License in California
    - BLS and ACLS certification
    - Minimum 3 years acute care nursing experience
    - Proficiency with Epic EHR
    """
    nurse_resume = """
    Jane Doe, RN
    Active California RN License #987654
    Certifications: BLS, ACLS
    Experience: 4 years nursing in Med-Surg and Telemetry units.
    EHR: Epic, Cerner.
    """
    reqs = await extractor.extract_requirements(nursing_jd)
    assert len(reqs) >= 3

    result = await extractor.evaluate_matches(reqs, nurse_resume)
    assert result.weighted_score >= 60.0
    assert len(result.strengths) >= 2
