import pytest
from app.core.learning.knowledge_store import KnowledgeStore
from app.models.learning_models import Pattern

@pytest.mark.asyncio
async def test_save_and_retrieve_pattern():
    store = KnowledgeStore()
    pattern = Pattern(
        id="test_001",
        type="domain_detection",
        context={"resume_domain": "architecture", "jd_domain": "ai"},
        rule="Domain mismatch = score < 20",
        confidence=0.8
    )
    await store.save_pattern(pattern)
    patterns = await store.get_patterns("domain_detection")
    assert len(patterns) > 0

@pytest.mark.asyncio
async def test_get_stats():
    store = KnowledgeStore()
    stats = await store.get_stats()
    assert stats.total_patterns >= 0
    assert stats.total_feedback >= 0
