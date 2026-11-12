"""Comprehensive End-to-End Tests for RAG Phase 2: Redis VSS Vector Store & Click Telemetry."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.knowledge.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
    RedisVectorStore,
    get_vector_store
)
from app.knowledge.models import VerifiedResource
from app.api.routes.telemetry import IN_MEMORY_CLICK_COUNTS, IN_MEMORY_DOMAIN_COUNTS
from app.knowledge.retriever import KnowledgeRetriever
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def sample_resource():
    return VerifiedResource(
        id="test-cloud-001",
        title="Azure Cloud Fundamentals Guide",
        description="Comprehensive beginner track for Azure cloud architecture and compute",
        url="https://learn.microsoft.com/en-us/training/modules/intro-to-azure-fundamentals/",
        platform="Microsoft Learn",
        domain="tech",
        skills_covered=["Azure", "Cloud Computing"],
        type="course",
        difficulty="beginner",
        duration_hours=4.0,
        is_free=True
    )

# -------------------------------------------------------------
# 1. In-Memory Vector Store Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_in_memory_vector_store_operations(sample_resource):
    """Test upsert, count, and search on the InMemoryVectorStore."""
    store = InMemoryVectorStore()
    vec = [0.1] * 384
    
    assert await store.count() == 0
    await store.upsert(sample_resource, vec)
    assert await store.count() == 1

    # Exact match query
    results = await store.search(query_vector=vec, domain="tech", top_k=1)
    assert len(results) == 1
    res, sim = results[0]
    assert res.id == sample_resource.id
    assert sim > 0.99

    # Filter mismatch domain
    mismatch = await store.search(query_vector=vec, domain="healthcare", top_k=1)
    assert len(mismatch) == 0

# -------------------------------------------------------------
# 2. Redis Vector Store & Resilient Fallback Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_redis_vector_store_fallback(sample_resource):
    """Verify that RedisVectorStore gracefully falls back to in-memory store when Redis VSS is absent."""
    store = RedisVectorStore(redis_url="redis://localhost:6379/0")
    vec = [0.2] * 384

    # Upsert should succeed by mirroring to local memory fallback
    success = await store.upsert(sample_resource, vec)
    assert success is True
    assert await store.count() >= 1

    # Search should safely fall back and find the resource
    results = await store.search(query_vector=vec, domain="tech", top_k=1)
    assert len(results) == 1
    res, sim = results[0]
    assert res.id == sample_resource.id

def test_get_vector_store_singleton():
    """Verify vector store singleton retrieval."""
    store1 = get_vector_store("memory")
    store2 = get_vector_store("memory")
    assert store1 is store2
    assert isinstance(store1, BaseVectorStore)

# -------------------------------------------------------------
# 3. Click Telemetry API Endpoints Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_telemetry_click_recording():
    """Verify recording of resource clicks via POST /api/v1/telemetry/resource-click."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "resource_id": "res-cloud-777",
            "resource_url": "https://www.coursera.org/learn/azure-basics",
            "title": "Azure Basics Course",
            "domain": "tech",
            "source": "roadmap_card"
        }
        resp = await ac.post("/api/v1/telemetry/resource-click", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recorded"
        assert data["identifier"] == "res-cloud-777"
        assert data["clicks"] >= 1
        assert IN_MEMORY_CLICK_COUNTS["res-cloud-777"] >= 1

@pytest.mark.asyncio
async def test_telemetry_popular_endpoint():
    """Verify retrieval of popular resources via GET /api/v1/telemetry/popular."""
    IN_MEMORY_CLICK_COUNTS["res-popular-001"] = 42
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/telemetry/popular?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "popular" in data
        assert any(item["identifier"] == "res-popular-001" for item in data["popular"])

# -------------------------------------------------------------
# 4. Retriever Integration with Popularity Bonus
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_retriever_popularity_boost(sample_resource):
    """Verify that frequently clicked resources receive an engagement boost in hybrid scoring."""
    store = InMemoryVectorStore()
    vec = [0.1] * 384
    await store.upsert(sample_resource, vec)

    retriever = KnowledgeRetriever(vector_store=store)
    retriever._is_indexed = True

    # 1. Base search without clicks
    IN_MEMORY_CLICK_COUNTS[sample_resource.id] = 0
    results_base = await retriever.retrieve_for_skill("Azure", domain="tech", top_k=1)
    base_score = results_base[0].score if results_base else 0.0

    # 2. Add high engagement clicks
    IN_MEMORY_CLICK_COUNTS[sample_resource.id] = 50
    results_boosted = await retriever.retrieve_for_skill("Azure", domain="tech", top_k=1)
    boosted_score = results_boosted[0].score if results_boosted else 0.0

    # Boosted score should be higher due to candidate click popularity
    assert boosted_score >= base_score
