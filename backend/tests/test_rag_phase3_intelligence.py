"""Comprehensive End-to-End Tests for RAG Phase 3: Context-Aware Reranker & Autonomous Ingestion."""
import pytest
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.knowledge.models import VerifiedResource, ResourceSearchResult
from app.knowledge.reranker import ContextualReranker, get_reranker
from app.knowledge.auto_ingest import AutonomousIngestionWorker, get_ingest_worker, DYNAMIC_CATALOG_FILE
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore

@pytest.fixture
def sample_candidates():
    beginner_res = VerifiedResource(
        id="res-beg-001",
        title="Introduction to Machine Learning Concepts",
        description="Beginner 101 overview of algorithms and basics",
        url="https://coursera.org/learn/ml-basics",
        platform="Coursera",
        domain="tech",
        skills_covered=["Machine Learning", "Python"],
        type="course",
        difficulty="beginner",
        duration_hours=2.0,
        is_free=True
    )
    advanced_res = VerifiedResource(
        id="res-adv-001",
        title="Deep Learning Systems Architecture & CUDA",
        description="Advanced engineering deep-dive into distributed training and GPU kernels",
        url="https://coursera.org/learn/deep-learning-systems",
        platform="Coursera",
        domain="tech",
        skills_covered=["Machine Learning", "Deep Learning"],
        type="certification",
        difficulty="advanced",
        duration_hours=25.0,
        is_free=False
    )
    return [
        ResourceSearchResult(resource=beginner_res, score=0.85, matched_skills=["Machine Learning"]),
        ResourceSearchResult(resource=advanced_res, score=0.88, matched_skills=["Machine Learning"])
    ]

# -------------------------------------------------------------
# 1. Contextual Reranker Tests (Seniority & Career Transition)
# -------------------------------------------------------------
def test_reranker_junior_preference(sample_candidates):
    """Junior candidate should receive beginner fundamentals over advanced materials."""
    reranker = ContextualReranker()
    reranked = reranker.rerank(
        query="Machine Learning",
        candidates=sample_candidates,
        seniority="junior",
        is_career_transition=False,
        top_k=2
    )

    # Beginner resource should jump to #1 for junior candidates
    assert reranked[0].resource.id == "res-beg-001"
    assert reranked[0].resource.difficulty == "beginner"

def test_reranker_senior_preference(sample_candidates):
    """Senior candidate should receive advanced/certification depth over 101 overviews."""
    reranker = ContextualReranker()
    reranked = reranker.rerank(
        query="Machine Learning",
        candidates=sample_candidates,
        seniority="senior",
        is_career_transition=False,
        top_k=2
    )

    # Advanced certification should rank #1 for senior candidates
    assert reranked[0].resource.id == "res-adv-001"
    assert reranked[0].resource.difficulty == "advanced"

def test_reranker_career_transition_boost(sample_candidates):
    """Career switcher transitioning domain should receive boosted beginner foundations."""
    reranker = ContextualReranker()
    # Even if listed as mid seniority, career transition flag boosts foundational resources
    reranked = reranker.rerank(
        query="Machine Learning",
        candidates=sample_candidates,
        seniority="mid",
        is_career_transition=True,
        top_k=2
    )

    assert reranked[0].resource.id == "res-beg-001"

# -------------------------------------------------------------
# 2. Autonomous Dynamic Ingestion Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_autonomous_ingestion_discovery_and_commit():
    """Verify that an unseen skill gap triggers discovery, schema creation, and catalog persistence."""
    worker = AutonomousIngestionWorker()

    # Mock replacer search to avoid third party API calls during test
    mock_url = "https://www.coursera.org/search?query=Quantum+Circuit+Synthesis"
    with patch.object(worker.replacer, "find_course_replacement", return_value=mock_url):
        resource = await worker.ingest_skill("Quantum Circuit Synthesis", domain="tech")

        assert resource is not None
        assert "Quantum" in resource.title
        assert resource.url == mock_url
        assert resource.platform == "Coursera"
        assert "Quantum Circuit Synthesis" in resource.skills_covered

        # Verify dynamic catalog file persistence
        assert os.path.exists(DYNAMIC_CATALOG_FILE)
        with open(DYNAMIC_CATALOG_FILE, "r", encoding="utf-8") as f:
            catalog_items = json.load(f)
            assert any(item.get("id") == resource.id for item in catalog_items)

# -------------------------------------------------------------
# 3. Knowledge Retriever End-to-End Integration with Reranker & Ingestion
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_retriever_contextual_flow(sample_candidates):
    """Verify that retriever passes seniority context to the reranker and isolates custom store."""
    from app.knowledge.bm25_scorer import get_bm25_index
    from app.knowledge.semantic_cache import get_semantic_cache

    bm25 = get_bm25_index()
    prev_corpus = dict(bm25.corpus)
    bm25.index_resources([item.resource for item in sample_candidates])
    get_semantic_cache().clear()

    try:
        store = InMemoryVectorStore()
        for item in sample_candidates:
            await store.upsert(item.resource, [0.1] * 384)

        retriever = KnowledgeRetriever(vector_store=store)
        retriever._is_indexed = True

        # 1. Test junior retrieval
        junior_res = await retriever.retrieve_for_skill("Machine Learning", domain="tech", seniority="junior", top_k=1)
        assert len(junior_res) == 1
        diff_val = getattr(junior_res[0].resource.difficulty, "value", str(junior_res[0].resource.difficulty))
        assert diff_val == "beginner"

        # 2. Test senior retrieval
        senior_res = await retriever.retrieve_for_skill("Machine Learning", domain="tech", seniority="senior", top_k=1)
        assert len(senior_res) == 1
        senior_diff = getattr(senior_res[0].resource.difficulty, "value", str(senior_res[0].resource.difficulty))
        assert senior_diff == "advanced"

        # 3. Test unseen skill query completes safely without raising
        unseen = await retriever.retrieve_for_skill("HyperNicheNonExistentSkillXYZ123", domain="tech")
        assert isinstance(unseen, list)
    finally:
        bm25.index_resources(list(prev_corpus.values()))
        get_semantic_cache().clear()
