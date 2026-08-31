import pytest
from app.core.learning.pattern_extractor import PatternExtractor
from app.models.learning_models import Feedback

@pytest.mark.asyncio
async def test_extract_domain_pattern():
    extractor = PatternExtractor()
    feedback = Feedback(
        analysis_id="test_123",
        rating=5,
        correction={"domain": "architecture", "domain_rule": "Architecture vs AI = mismatch penalty"},
        feedback_type="explicit"
    )
    context = {
        "resume_domain": "architecture",
        "jd_domain": "ai",
        "keywords": ["building", "machine learning"]
    }
    patterns = await extractor.extract_from_feedback(feedback, context)
    assert len(patterns) > 0
    assert patterns[0].type == "domain_detection"
    assert patterns[0].confidence >= 0.5
