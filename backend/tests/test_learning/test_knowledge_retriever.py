import pytest
from app.core.learning.knowledge_retriever import KnowledgeRetriever

@pytest.mark.asyncio
async def test_retrieve_matching_patterns():
    retriever = KnowledgeRetriever()
    context = {
        "resume_domain": "architecture",
        "jd_domain": "ai"
    }
    matches = await retriever.retrieve(context, max_patterns=3)
    if matches:
        assert all(m.relevance_score > 0.3 for m in matches)
