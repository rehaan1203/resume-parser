"""Hermetic unit tests for RAG Knowledge Base and Isolation (Stage 2)."""
import pytest
import os
from unittest.mock import AsyncMock, patch
from app.knowledge.models import VerifiedResource, ResourceType, DifficultyLevel
from app.knowledge.embedding_service import EmbeddingService
from app.knowledge.vector_store import InMemoryVectorStore
from app.knowledge.retriever import KnowledgeRetriever, CATALOG_DIR
from app.ai.career_advisor import CareerAdvisor

def test_embedding_service_deterministic():
    service = EmbeddingService(dimension=128)
    vec1 = service.get_deterministic_embedding("FastAPI Python Microservices")
    vec2 = service.get_deterministic_embedding("FastAPI Python Microservices")
    assert vec1 == vec2
    assert len(vec1) == 128
    # Norm check (approx 1.0)
    norm = sum(x * x for x in vec1)
    assert 0.99 <= norm <= 1.01

@pytest.mark.asyncio
async def test_vector_store_upsert_and_search():
    store = InMemoryVectorStore()
    service = EmbeddingService(dimension=128)

    res1 = VerifiedResource(
        id="tech-docker",
        title="Docker Container Fundamentals",
        url="https://docker.com",
        platform="Docker",
        type=ResourceType.COURSE,
        domain="tech",
        skills_covered=["docker", "containers"],
        description="Learn docker containerization and compose"
    )
    vec1 = service.get_deterministic_embedding(f"{res1.title} {res1.description}")
    await store.upsert(res1, vec1)

    res2 = VerifiedResource(
        id="health-bls",
        title="Basic Life Support Guide",
        url="https://cpr.heart.org",
        platform="AHA",
        type=ResourceType.CERTIFICATION,
        domain="healthcare",
        skills_covered=["bls", "cpr"],
        description="Life support emergency response"
    )
    vec2 = service.get_deterministic_embedding(f"{res2.title} {res2.description}")
    await store.upsert(res2, vec2)

    assert await store.count() == 2

    # Search with domain filter "tech"
    query_vec = service.get_deterministic_embedding("docker")
    tech_results = await store.search(query_vec, domain="tech", top_k=2)
    assert len(tech_results) == 1
    assert tech_results[0][0].id == "tech-docker"

    # Search with domain filter "healthcare"
    health_results = await store.search(query_vec, domain="healthcare", top_k=2)
    assert len(health_results) == 1
    assert health_results[0][0].id == "health-bls"

@pytest.mark.asyncio
async def test_knowledge_retriever_multi_domain_catalogs():
    retriever = KnowledgeRetriever()
    count = await retriever.initialize_and_index_catalogs()
    assert count >= 10

    # Tech query
    tech_res = await retriever.retrieve_for_skill("Docker", domain="tech", top_k=1)
    assert len(tech_res) >= 1
    assert "docker" in tech_res[0].resource.title.lower() or "docker" in [s.lower() for s in tech_res[0].resource.skills_covered]

    # Healthcare query
    health_res = await retriever.retrieve_for_skill("BLS", domain="healthcare", top_k=1)
    assert len(health_res) >= 1
    assert "bls" in health_res[0].resource.title.lower() or "bls" in [s.lower() for s in health_res[0].resource.skills_covered]

    # Trades query
    trades_res = await retriever.retrieve_for_skill("EPA 608", domain="trades", top_k=1)
    assert len(trades_res) >= 1
    assert "epa" in trades_res[0].resource.title.lower()

    # Legal query
    legal_res = await retriever.retrieve_for_skill("Contract Drafting", domain="legal", top_k=1)
    assert len(legal_res) >= 1
    assert "contract" in legal_res[0].resource.title.lower()

@pytest.mark.asyncio
async def test_rag_isolation_fail_closed():
    """Verify that if the vector retriever throws an exception, CareerAdvisor still succeeds gracefully."""
    mock_client = AsyncMock()
    mock_client.generate_structured_content = AsyncMock(return_value={
        "advice": {
            "short_term_goals": ["Study fundamentals"],
            "long_term_goals": ["Reach senior level"],
            "skills_to_develop": [{"skill": "Docker", "priority": "high", "resources": []}],
            "career_paths": [{"title": "DevOps Engineer", "description": "Cloud lead", "timeline": "2 years"}],
            "recommended_roles": ["DevOps"],
            "salary_expectations": {"range": "$120k", "factors": ["Experience"]}
        }
    })

    # Broken retriever that raises exception
    broken_retriever = KnowledgeRetriever()
    broken_retriever.retrieve_for_skill_gaps = AsyncMock(side_effect=RuntimeError("Vector DB connection timeout"))

    advisor = CareerAdvisor(client=mock_client, retriever=broken_retriever)
    advice = await advisor.get_advice(
        resume="Software Engineer with Python",
        experience="3 years",
        goals="Cloud architect",
        skill_gaps=["Docker"]
    )

    # Core response must still succeed without throwing an uncaught exception
    assert advice is not None
    assert "short_term_goals" in advice
    assert len(advice["skills_to_develop"]) >= 1

