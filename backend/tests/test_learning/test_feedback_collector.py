import pytest
from app.core.learning.feedback_collector import FeedbackCollector

@pytest.mark.asyncio
async def test_collect_explicit_feedback():
    collector = FeedbackCollector()
    feedback = await collector.collect_explicit(
        analysis_id="test_123",
        rating=5,
        comment="Excellent analysis",
        corrections={"score": 85}
    )
    assert feedback.rating == 5
    assert feedback.feedback_type == "explicit"
    assert feedback.correction == {"score": 85}

@pytest.mark.asyncio
async def test_collect_implicit_feedback():
    collector = FeedbackCollector()
    session_data = {
        "resubmitted": True,
        "time_spent_seconds": 30
    }
    feedback = await collector.collect_implicit("test_123", session_data)
    assert feedback.rating == 1
