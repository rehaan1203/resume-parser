import pytest
from app.core.quality.quality_checker import QualityChecker

def test_quality_scoring_domain_mismatch():
    """Test quality checker calculates correct scores for domain mismatch."""
    checker = QualityChecker()
    output = {
        "domain_match": False,
        "overall_score": 80,  # CRITICAL ERROR: mismatch but score > 20
        "skill_gaps": ["1", "2", "3"],
        "reasoning": "some brief reasoning here",
        "friction_points": [],
        "strengths": []
    }
    
    score = checker.check(output)
    
    # Domain Match Logic score should be 0 because it's a critical error
    domain_criteria = next(c for c in score.criteria if c.name == "Domain Match Logic")
    assert domain_criteria.score == 0
    assert not score.passed
