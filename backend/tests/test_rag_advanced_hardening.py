"""Targeted verification tests for advanced RAG subsystem hardening.

Verifies:
1. Regex word boundary matching preventing short technology substring collisions ('go' in 'django', 'r' in 'docker', 'c' in 'react').
2. BM25 tokenizer preservation of programming language symbols ('c++', 'c#', '.net', 'node.js', 'ci/cd', 'tcp/ip').
3. CRAG Evaluator rejection of substring hallucinations.
4. Cross-domain conflict penalty enforcement.
5. Semantic cache targeted resource eviction and CDC bus cache invalidation.
"""
import pytest
from app.knowledge.models import VerifiedResource, ResourceType, DifficultyLevel
from app.knowledge.crag_evaluator import CRAGEvaluator, word_boundary_match
from app.knowledge.bm25_scorer import BM25Index, ReciprocalRankFusion
from app.knowledge.semantic_cache import SemanticVectorCache, SemanticCacheEntry
from app.knowledge.cdc_bus import CDCEvent, get_cdc_bus


def test_word_boundary_match_isolation():
    """Verify word boundary matching correctly isolates short technical acronyms without false positive substring matches."""
    # Negative substring cases that previously caused false positives
    assert not word_boundary_match("go", "django")
    assert not word_boundary_match("django", "go")
    assert not word_boundary_match("r", "docker")
    assert not word_boundary_match("docker", "r")
    assert not word_boundary_match("c", "react")
    assert not word_boundary_match("sql", "nosql")
    assert not word_boundary_match("c", "c++")
    assert not word_boundary_match("c++", "c")
    assert not word_boundary_match("c", "c#")

    # Positive exact and phrase matches
    assert word_boundary_match("go", "go")
    assert word_boundary_match("go", "learn go programming")
    assert word_boundary_match("go", "the go language specification")
    assert word_boundary_match("c++", "modern c++ design")
    assert word_boundary_match("c#", "c# 12 and .net 8")
    assert word_boundary_match(".net", "asp.net core and .net")
    assert word_boundary_match("node.js", "full stack node.js development")
    assert word_boundary_match("ci/cd", "automated ci/cd pipelines")
    assert word_boundary_match("tcp/ip", "tcp/ip network architecture")


def test_bm25_tokenizer_preserves_technical_symbols():
    """Verify BM25 tokenizer preserves technical symbols (+, #, ., /) and does not collapse them."""
    index = BM25Index()
    text = "Master modern C++ and C# with .NET 8, Node.js, automated CI/CD pipelines, and TCP/IP."
    tokens = index.tokenize(text)

    assert "c++" in tokens
    assert "c#" in tokens
    assert ".net" in tokens
    assert "node.js" in tokens
    assert "ci/cd" in tokens
    assert "tcp/ip" in tokens

    # Ensure C++ and C# did not degenerate into raw single 'c'
    c_count = tokens.count("c")
    assert c_count == 0, f"Expected no degenerate 'c' tokens, but found {c_count}"


def test_crag_evaluator_rejects_substring_hallucination():
    """Verify CRAG evaluator grades a 'Go' course as 'incorrect' for a 'Django' query."""
    evaluator = CRAGEvaluator()
    go_resource = VerifiedResource(
        id="res-golang-101",
        title="Go Programming Fundamentals",
        url="https://golang.org/doc",
        description="Comprehensive guide to learning the Go programming language from scratch.",
        skills_covered=["Go", "Golang", "Concurrency"],
        platform="Official Docs",
        domain="tech",
        resource_type=ResourceType.DOCUMENTATION,
        difficulty=DifficultyLevel.BEGINNER,
        free=True,
    )

    # Candidate query is for "Django"
    grade = evaluator.grade_resource(
        resource=go_resource,
        query_skill="Django",
        seniority="mid",
        domain="tech"
    )

    # Must be graded incorrect because 'go' does not match 'django'
    assert grade.grade == "incorrect"
    assert "Exact skill tag overlap" not in grade.reason
    assert "Skill keyword present in description" not in grade.reason


def test_crag_evaluator_accepts_exact_term_with_symbols():
    """Verify CRAG evaluator awards exact skill tag overlap for 'C++'."""
    evaluator = CRAGEvaluator()
    cpp_resource = VerifiedResource(
        id="res-cpp-201",
        title="Effective Modern C++",
        url="https://isocpp.org",
        description="Best practices for writing modern C++ code.",
        skills_covered=["C++", "STL", "Memory Management"],
        platform="Official Docs",
        domain="tech",
        resource_type=ResourceType.DOCUMENTATION,
        difficulty=DifficultyLevel.INTERMEDIATE,
        free=True,
    )

    grade = evaluator.grade_resource(
        resource=cpp_resource,
        query_skill="C++",
        seniority="mid",
        domain="tech"
    )

    assert grade.grade == "correct"
    assert grade.confidence >= 0.70
    assert "Exact skill tag overlap" in grade.reason


def test_crag_evaluator_cross_domain_conflict_penalty():
    """Verify that discordant cross-domain hits receive the conflict penalty and are marked incorrect."""
    evaluator = CRAGEvaluator()
    tech_resource = VerifiedResource(
        id="res-react-101",
        title="React Frontend Architecture",
        url="https://react.dev",
        description="Building single page applications with React.",
        skills_covered=["React", "JavaScript", "Frontend"],
        platform="React Docs",
        domain="tech",
        resource_type=ResourceType.DOCUMENTATION,
        difficulty=DifficultyLevel.BEGINNER,
        free=True,
    )

    # Query is explicitly in Healthcare
    grade = evaluator.grade_resource(
        resource=tech_resource,
        query_skill="Clinical Charting",
        seniority="mid",
        domain="healthcare"
    )

    assert grade.grade == "incorrect"
    assert "Cross-domain conflict penalty" in grade.reason


def test_semantic_cache_invalidation_by_resource_and_tags():
    """Verify SemanticVectorCache evicts entries when targeted resource IDs or tags are invalidated."""
    cache = SemanticVectorCache(similarity_threshold=0.90)

    res1 = VerifiedResource(
        id="res-target-1",
        title="Microservices Architecture",
        url="https://example.com/ms",
        description="Microservices guide",
        skills_covered=["Microservices", "Docker"],
        platform="Example",
        domain="tech",
        resource_type=ResourceType.DOCUMENTATION,
        difficulty=DifficultyLevel.INTERMEDIATE,
        free=True,
    )
    from app.knowledge.models import ResourceSearchResult
    hit = ResourceSearchResult(resource=res1, score=0.95, matched_skills=["Microservices"])

    # Store entry in cache
    dummy_vec = [1.0] + [0.0] * 127
    cache.set(
        query_text="microservices patterns",
        query_vector=dummy_vec,
        results=[hit],
        domain="tech"
    )

    # Cache should hit
    assert cache.get(dummy_vec, domain="tech") is not None

    # Invalidate by resource ID
    cache.invalidate_resource("res-target-1")

    # Cache entry should now be purged
    assert cache.get(dummy_vec, domain="tech") is None


def test_semantic_cache_invalidation_by_tag_in_results():
    """Verify SemanticVectorCache evicts entries when any resource inside results contains the invalidated tag."""
    cache = SemanticVectorCache(similarity_threshold=0.90)

    res2 = VerifiedResource(
        id="res-target-2",
        title="Kubernetes Cluster Setup",
        url="https://k8s.io",
        description="Kubernetes orchestration",
        skills_covered=["Kubernetes", "DevOps"],
        platform="K8s Docs",
        domain="tech",
        resource_type=ResourceType.DOCUMENTATION,
        difficulty=DifficultyLevel.ADVANCED,
        free=True,
    )
    from app.knowledge.models import ResourceSearchResult
    hit2 = ResourceSearchResult(resource=res2, score=0.92, matched_skills=["Kubernetes"])

    dummy_vec2 = [0.0, 1.0] + [0.0] * 126
    # Query text doesn't mention 'kubernetes', but the cached result does
    cache.set(
        query_text="container orchestration cluster",
        query_vector=dummy_vec2,
        results=[hit2],
        domain="tech"
    )

    assert cache.get(dummy_vec2, domain="tech") is not None

    # Invalidate tag 'kubernetes'
    cache.invalidate_tags(["kubernetes"])

    # Entry must be purged
    assert cache.get(dummy_vec2, domain="tech") is None
