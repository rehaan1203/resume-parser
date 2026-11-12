"""Comprehensive Test Suite for Stage 5 Advanced RAG Innovations.

Tests:
1. Temporal Video Deep-Linking (Timestamped Video RAG)
2. Recency-Aware RAG & Tech Depreciation Guard
3. Self-Querying & Constraint Filter Synthesizer
4. Contextual Fluff Compressor & Syllabus Extractor
5. Multi-Modal Visual Architecture RAG (Mermaid Schematics)
6. End-to-End Retriever Integration
"""
import os
import pytest
from app.knowledge.models import VerifiedResource, ResourceType, QueryConstraints, VideoChapter
from app.knowledge.recency_scorer import get_recency_scorer
from app.knowledge.self_query import get_self_query_synthesizer
from app.knowledge.compressor import get_contextual_compressor
from app.knowledge.retriever import KnowledgeRetriever

os.environ["RAG_EMBEDDING_PROVIDER"] = "deterministic"

@pytest.fixture
def recency_scorer():
    return get_recency_scorer()

@pytest.fixture
def self_query_synthesizer():
    return get_self_query_synthesizer()

@pytest.fixture
def compressor():
    return get_contextual_compressor()


def test_recency_scorer_exponential_decay(recency_scorer):
    """Verify recency scorer applies exponential decay with domain-adaptive half-lives."""
    res_recent_tech = VerifiedResource(
        id="tech-recent",
        title="Modern Python 3.12 & FastAPI",
        url="https://example.com/fastapi",
        platform="FastAPI Docs",
        domain="tech",
        skills_covered=["python", "fastapi"],
        difficulty="beginner",
        duration_hours=4.0,
        publication_year=2026,
        description="Current Python microservice development."
    )

    res_old_tech = VerifiedResource(
        id="tech-old",
        title="Legacy Python 2.7 Web Services",
        url="https://example.com/py2",
        platform="Legacy Web",
        domain="tech",
        skills_covered=["python"],
        difficulty="beginner",
        duration_hours=4.0,
        publication_year=2018,
        description="Legacy Python 2.7 tutorials."
    )

    res_old_legal = VerifiedResource(
        id="legal-old",
        title="Principles of Contract Law & Mutual Assent",
        url="https://example.com/contracts",
        platform="Legal Archive",
        domain="legal",
        skills_covered=["contract law"],
        difficulty="beginner",
        duration_hours=10.0,
        publication_year=2018,
        description="Fundamental common law contract principles."
    )

    mult_recent = recency_scorer.calculate_recency_multiplier(res_recent_tech, current_year=2026)
    mult_old_tech = recency_scorer.calculate_recency_multiplier(res_old_tech, current_year=2026)
    mult_old_legal = recency_scorer.calculate_recency_multiplier(res_old_legal, current_year=2026)

    # Recent tech should have no penalty
    assert mult_recent >= 0.95
    # 8-year-old tech should have substantial decay
    assert mult_old_tech <= 0.40
    # 8-year-old legal should decay much slower than tech due to longer half-life
    assert mult_old_legal > mult_old_tech
    # Verify deprecation flag
    assert recency_scorer.is_deprecated(res_old_tech, current_year=2026) is True
    assert recency_scorer.is_deprecated(res_recent_tech, current_year=2026) is False


def test_self_querying_constraint_synthesizer(self_query_synthesizer):
    """Verify constraint synthesizer parses free/paid, duration limits, and platforms."""
    query = "Find a free course under 5 hours on youtube for beginners"
    constraints = self_query_synthesizer.synthesize_constraints(query)

    assert constraints.is_free is True
    assert constraints.max_duration_hours == 5.0
    assert "YouTube" in constraints.required_platforms

    # Test matching vs violating resources
    res_matching = VerifiedResource(
        id="res-match",
        title="Docker Quickstart Tutorial",
        url="https://youtube.com/watch?v=123",
        platform="YouTube",
        type=ResourceType.YOUTUBE_VIDEO,
        domain="tech",
        skills_covered=["docker"],
        difficulty="beginner",
        duration_hours=2.5,
        is_free=True,
        description="Quick Docker tutorial on YouTube."
    )

    res_too_long = VerifiedResource(
        id="res-long",
        title="Massive Docker Masterclass",
        url="https://youtube.com/watch?v=456",
        platform="YouTube",
        type=ResourceType.YOUTUBE_VIDEO,
        domain="tech",
        skills_covered=["docker"],
        difficulty="beginner",
        duration_hours=18.0,
        is_free=True,
        description="18-hour deep dive."
    )

    res_paid = VerifiedResource(
        id="res-paid",
        title="Commercial Paid Docker Certification",
        url="https://example.com/paid",
        platform="Paid Platform",
        type=ResourceType.COURSE,
        domain="tech",
        skills_covered=["docker"],
        difficulty="beginner",
        duration_hours=4.0,
        is_free=False,
        description="Paid training."
    )

    assert self_query_synthesizer.matches_constraints(res_matching, constraints) is True
    assert self_query_synthesizer.matches_constraints(res_too_long, constraints) is False
    assert self_query_synthesizer.matches_constraints(res_paid, constraints) is False


def test_contextual_fluff_compressor(compressor):
    """Verify compressor strips marketing copy while retaining concrete syllabus details."""
    fluffy_text = (
        "Join over 250,000 students! Enroll now for free with a 30-day money-back guarantee. "
        "Rated 4.9 out of 5 stars by industry engineers. "
        "Learn Docker containerization, Dockerfile architecture, multi-stage builds, volume mounting, "
        "and deploying multi-container services with Docker Compose."
    )

    compressed = compressor.compress_description(fluffy_text)

    # Fluff must be stripped
    assert "250,000" not in compressed
    assert "money-back guarantee" not in compressed
    assert "Rated 4.9" not in compressed

    # Concrete technical terms must be preserved
    assert "Docker containerization" in compressed
    assert "Dockerfile" in compressed
    assert "Docker Compose" in compressed


def test_multimodal_diagram_retriever():
    """Verify diagram retriever loads and matches system architecture schematics."""
    retriever = KnowledgeRetriever()
    diags = retriever.get_diagrams_for_skills(["kubernetes", "docker"], domain="tech")

    assert len(diags) > 0
    k8s_diag = diags[0]
    assert "kubernetes" in k8s_diag.title.lower() or "pod" in k8s_diag.title.lower()
    assert "graph td" in k8s_diag.mermaid_definition.lower()
    assert "ingress" in k8s_diag.mermaid_definition.lower()

    # Finance diagram matching
    fin_diags = retriever.get_diagrams_for_skills(["dcf_valuation"], domain="finance")
    assert len(fin_diags) > 0
    assert "dcf" in fin_diags[0].id.lower() or "valuation" in fin_diags[0].title.lower()


@pytest.mark.asyncio
async def test_temporal_video_chapter_deeplinking():
    """Verify that querying a specific subtopic returns a timestamped deep-link."""
    retriever = KnowledgeRetriever()
    await retriever.initialize_and_index_catalogs()

    # Query for Docker compose specifically
    results = await retriever.retrieve_for_skill("docker compose", domain="tech", top_k=2)
    assert len(results) > 0

    video_results = [r.resource for r in results if r.resource.type == ResourceType.YOUTUBE_VIDEO]
    if video_results:
        res = video_results[0]
        # Check that active_timestamp_url was synthesized with a timestamp anchor
        assert res.active_timestamp_url is not None
        assert "t=" in res.active_timestamp_url
        assert res.matched_chapter is not None
        assert "compose" in res.matched_chapter.lower() or "docker" in res.matched_chapter.lower()


@pytest.mark.asyncio
async def test_end_to_end_stage5_retriever_search():
    """Verify search_for_gaps end-to-end integration with constraints and diagram matching."""
    retriever = KnowledgeRetriever()
    await retriever.initialize_and_index_catalogs()

    constraints = QueryConstraints(is_free=True, max_duration_hours=12.0)
    resources = await retriever.search_for_gaps(
        skills=["docker", "kubernetes"],
        domain="tech",
        limit=4,
        constraints=constraints
    )

    assert len(resources) > 0
    assert all(r.is_free is True for r in resources)
    assert all(r.duration_hours is None or r.duration_hours <= 12.0 for r in resources)

    # Fetch diagrams for the same skills
    diags = retriever.get_diagrams_for_skills(["docker", "kubernetes"], domain="tech")
    assert len(diags) > 0
    assert len(diags[0].mermaid_definition) > 20

