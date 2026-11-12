"""Comprehensive Test Suite for Stage 4 Advanced RAG: GraphRAG, HyDE, and CRAG."""
import os
import pytest
import asyncio
from app.knowledge.models import VerifiedResource, ResourceSearchResult
from app.knowledge.graph_store import SkillDependencyGraph, get_skill_graph
from app.knowledge.hyde_expander import HyDEExpander, get_hyde_expander
from app.knowledge.crag_evaluator import CRAGEvaluator, get_crag_evaluator
from app.knowledge.retriever import KnowledgeRetriever

os.environ["RAG_EMBEDDING_PROVIDER"] = "deterministic"

@pytest.fixture
def skill_graph():
    return get_skill_graph()

@pytest.fixture
def hyde_expander():
    return get_hyde_expander()

@pytest.fixture
def crag_evaluator():
    return get_crag_evaluator()


def test_skill_graph_dag_loading_and_acyclicity(skill_graph):
    """Verify that graph loads successfully and passes cycle detection."""
    assert len(skill_graph.nodes) >= 30
    assert skill_graph._validate_acyclic() is True
    # Verify presence of multi-domain nodes
    assert skill_graph.find_node("kubernetes") is not None
    assert skill_graph.find_node("dcf_valuation") is not None
    assert skill_graph.find_node("hipaa_compliance_governance") is not None
    assert skill_graph.find_node("contract_drafting_analysis") is not None
    assert skill_graph.find_node("plc_ladder_logic") is not None


def test_graphrag_topological_prerequisite_resolution(skill_graph):
    """Verify multi-hop prerequisite resolution returns dependencies in correct pedagogical order."""
    unfulfilled = skill_graph.resolve_prerequisites(
        target_skills=["kubernetes"],
        candidate_known_skills=["python"]
    )
    unfulfilled_ids = [n.id for n in unfulfilled]
    assert "linux_basics" in unfulfilled_ids
    assert "docker_containers" in unfulfilled_ids
    assert "kubernetes_orchestration" in unfulfilled_ids

    # Topological order: linux before docker before k8s
    idx_linux = unfulfilled_ids.index("linux_basics")
    idx_docker = unfulfilled_ids.index("docker_containers")
    idx_k8s = unfulfilled_ids.index("kubernetes_orchestration")
    assert idx_linux < idx_docker < idx_k8s


def test_graphrag_candidate_filtering(skill_graph):
    """Verify that skills candidate already possesses are filtered out from prerequisite chain."""
    unfulfilled = skill_graph.resolve_prerequisites(
        target_skills=["kubernetes"],
        candidate_known_skills=["linux_basics", "docker_containers"]
    )
    unfulfilled_ids = [n.id for n in unfulfilled]
    assert "linux_basics" not in unfulfilled_ids
    assert "docker_containers" not in unfulfilled_ids
    assert "kubernetes_orchestration" in unfulfilled_ids


@pytest.mark.asyncio
async def test_hyde_syllabus_expansion(hyde_expander):
    """Verify HyDE expands concise keywords into rich syllabi with zero delay."""
    q_k8s = await hyde_expander.expand("kubernetes", domain="tech")
    assert "container orchestration" in q_k8s.hypothetical_curriculum.lower()
    assert len(q_k8s.hypothetical_curriculum) > 50

    q_fin = await hyde_expander.expand("dcf_valuation", domain="finance")
    assert "cash flow" in q_fin.hypothetical_curriculum.lower()

    q_novel = await hyde_expander.expand("unseen_custom_tool", domain="tech")
    assert "comprehensive" in q_novel.hypothetical_curriculum.lower()


def test_crag_evaluator_grading_accuracy(crag_evaluator):
    """Verify CRAG grades valid vs invalid resources accurately."""
    res_valid = VerifiedResource(
        id="k8s-res",
        title="Kubernetes Cluster Administration Guide",
        url="https://kubernetes.io/docs/",
        platform="Kubernetes.io",
        domain="tech",
        skills_covered=["kubernetes", "docker"],
        difficulty="intermediate",
        type="documentation",
        duration_hours=6.0,
        description="Comprehensive production cluster deployment guide for Kubernetes."
    )

    res_invalid = VerifiedResource(
        id="nurse-res",
        title="Emergency Bedside Nursing Protocols",
        url="https://example.com/nursing",
        platform="Hospital Med",
        domain="healthcare",
        skills_covered=["triage", "bedside care"],
        difficulty="beginner",
        type="course",
        duration_hours=12.0,
        description="Hospital emergency department clinical triage."
    )

    grade_good = crag_evaluator.grade_resource(res_valid, "kubernetes", seniority="mid", domain="tech")
    assert grade_good.grade in ["correct", "ambiguous"]
    assert grade_good.confidence >= 0.70

    grade_bad = crag_evaluator.grade_resource(res_invalid, "kubernetes", seniority="mid", domain="tech")
    assert grade_bad.grade == "incorrect"
    assert grade_bad.confidence < 0.40


def test_crag_query_transformation(crag_evaluator):
    """Verify query transformation adapts anchors for junior vs senior."""
    q_jr = crag_evaluator.transform_query("docker", domain="tech", seniority="entry")
    assert "fundamentals" in q_jr.lower() or "beginner" in q_jr.lower()

    q_sr = crag_evaluator.transform_query("docker", domain="tech", seniority="senior")
    assert "advanced" in q_sr.lower() or "certification" in q_sr.lower()


@pytest.mark.asyncio
async def test_end_to_end_retriever_stage4_pipeline():
    """Verify complete retriever execution using GraphRAG, HyDE, and CRAG."""
    retriever = KnowledgeRetriever()
    await retriever.initialize_and_index_catalogs()

    # Search for missing 'kubernetes' when candidate only knows 'python'
    results = await retriever.search_for_gaps(
        skills=["kubernetes"],
        domain="tech",
        limit=3,
        seniority="junior",
        known_skills=["python"]
    )

    assert len(results) > 0
    # GraphRAG should introduce foundational Docker/Linux or K8s resources
    titles = [r.title.lower() for r in results]
    assert any("docker" in t or "kubernetes" in t or "linux" in t for t in titles)
    assert all(str(r.url).startswith("http") for r in results)

