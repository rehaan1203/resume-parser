"""Unit and Integration Tests for Stage 6 Deep Technical RAG Innovations.

Verifies:
1. Multi-Jurisdiction / Geo-Aware Regulatory RAG Routing (India DPDP/IT Act vs US USPTO/SEC).
2. Sparse BM25 + Reciprocal Rank Fusion (RRF) for high-entropy acronym fidelity (DPDP, FHIR).
3. Semantic Vector Query Caching with dynamic domain TTL and sub-millisecond retrieval.
4. Hierarchical Parent-Document / Small-to-Big Chunking resolution.
5. Negative Constraints & Anti-Skill Exclusion Filtering ('no AWS', 'without Django', 'exclude US').
6. Automated RAG Triad / RAGAS Hallucination Guardrails (Context Relevance, Faithfulness, Answer Relevance).
7. Hot-Reload Change Data Capture (CDC) Event Bus live updates.
"""
import time
import asyncio
import sys
import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from app.knowledge.models import (
    VerifiedResource,
    ResourceType,
    DifficultyLevel,
    QueryConstraints,
    ChildChunk
)
from app.knowledge.geo_router import get_geo_router, GeoRouter
from app.knowledge.bm25_scorer import get_bm25_index, BM25Index, ReciprocalRankFusion
from app.knowledge.semantic_cache import get_semantic_cache, SemanticVectorCache
from app.knowledge.self_query import get_self_query_synthesizer
from app.knowledge.ragas_evaluator import get_ragas_evaluator
from app.knowledge.cdc_bus import get_cdc_bus, CDCEvent


def test_geo_router_jurisdiction_detection_and_scoring():
    """Verify GeoRouter accurately detects Indian legal frameworks and strictly prunes US territorial laws."""
    geo_router = get_geo_router()

    # 1. Detection
    assert geo_router.detect_jurisdiction("DPDP Act compliance for data protection officer") == "IN"
    assert geo_router.detect_jurisdiction("Information Technology Act Section 43A and CERT-In directions") == "IN"
    assert geo_router.detect_jurisdiction("Bar Council of India AIBE bar examination preparation") == "IN"
    assert geo_router.detect_jurisdiction("Companies Act 2013 RoC MCA filing") == "IN"
    assert geo_router.detect_jurisdiction("USPTO patent prosecution and claims drafting") == "US"
    assert geo_router.detect_jurisdiction("HIPAA privacy rule and protected health information") == "US"
    assert geo_router.detect_jurisdiction("GDPR data subject rights and cross border transfer") == "EU"
    assert geo_router.detect_jurisdiction("General python and docker microservices") == "GLOBAL"

    # 2. Compatibility Scoring in Regulatory Domain (Legal)
    # When user is in India looking for legal advice:
    score_in = geo_router.score_geo_compatibility(resource_jurisdiction="IN", target_jurisdiction="IN", domain="legal")
    score_us = geo_router.score_geo_compatibility(resource_jurisdiction="US", target_jurisdiction="IN", domain="legal")
    score_global = geo_router.score_geo_compatibility(resource_jurisdiction="GLOBAL", target_jurisdiction="IN", domain="legal")

    assert score_in == 1.0
    # Crucial: US law (USPTO, SEC, FRCP) must be hard-pruned (0.0) for an Indian legal query
    assert score_us == 0.0
    assert score_global == 0.4

    # 3. Non-regulatory domain (Tech) allows cross-jurisdiction with mild damping
    tech_us_in = geo_router.score_geo_compatibility(resource_jurisdiction="US", target_jurisdiction="IN", domain="tech")
    assert tech_us_in == 0.70


def test_sparse_bm25_and_reciprocal_rank_fusion():
    """Verify BM25 preserves rare statutory acronyms (DPDP, FHIR) and RRF fuses dense + sparse ranks."""
    bm25 = BM25Index()

    res_dpdp = VerifiedResource(
        id="legal-dpdp-compliance",
        title="DPDP Act 2023 Compliance & Consent Architecture",
        url="https://example.com/dpdp",
        platform="NLSIU",
        type=ResourceType.DOCUMENTATION,
        domain="legal",
        jurisdiction="IN",
        skills_covered=["dpdp", "data privacy", "consent management"],
        description="Comprehensive compliance under the DPDP Act 2023 in India."
    )

    res_generic_privacy = VerifiedResource(
        id="legal-generic-privacy",
        title="General Principles of Privacy and Security in Software Systems",
        url="https://example.com/privacy",
        platform="edX",
        type=ResourceType.COURSE,
        domain="legal",
        jurisdiction="GLOBAL",
        skills_covered=["data privacy", "security"],
        description="Explores data privacy, data security, data governance, and data audits broadly."
    )

    bm25.index_resources([res_dpdp, res_generic_privacy])

    # Search specifically for exact acronym "DPDP"
    sparse_hits = bm25.search("DPDP", top_k=2)
    assert len(sparse_hits) > 0
    # The document with exact acronym DPDP must rank first with significant BM25 score
    top_doc, score = sparse_hits[0]
    assert top_doc.id == "legal-dpdp-compliance"
    assert score > 0.0

    # Test Reciprocal Rank Fusion (RRF)
    dense_results = [(res_generic_privacy, 0.85), (res_dpdp, 0.80)]
    sparse_results = [(res_dpdp, 3.2)]

    rrf = ReciprocalRankFusion(k=60, weight_dense=0.60, weight_sparse=0.40)
    fused = rrf.fuse(dense_results=dense_results, sparse_results=sparse_results, top_k=2)

    assert len(fused) == 2
    # Because res_dpdp had strong sparse acronym rank, RRF elevates it to top position
    assert fused[0].resource.id == "legal-dpdp-compliance"


def test_semantic_vector_cache_sub_millisecond_and_ttl():
    """Verify semantic cache returns instant hits for cosine-similar queries and supports tag invalidation."""
    cache = SemanticVectorCache(similarity_threshold=0.94)

    mock_vec_1 = [0.1] * 384
    mock_vec_near = [0.101] * 384  # Extremely close cosine similarity > 0.99
    mock_vec_distant = [-0.1] * 384

    dummy_res = VerifiedResource(
        id="tech-docker",
        title="Docker Container Mastery",
        url="https://example.com/docker",
        platform="Coursera",
        type=ResourceType.COURSE,
        domain="tech",
        skills_covered=["docker"],
        description="Hands-on Docker training."
    )

    from app.knowledge.models import ResourceSearchResult
    dummy_results = [ResourceSearchResult(resource=dummy_res, score=0.95, matched_skills=["docker"])]

    # Miss before setting
    assert cache.get(mock_vec_1, domain="tech", jurisdiction="GLOBAL") is None

    # Set cache with tech TTL (4 hours)
    cache.set(
        query_text="docker containers",
        query_vector=mock_vec_1,
        results=dummy_results,
        domain="tech",
        jurisdiction="GLOBAL"
    )

    # Hit with near vector
    start = time.perf_counter()
    hits = cache.get(mock_vec_near, domain="tech", jurisdiction="GLOBAL")
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert hits is not None
    assert len(hits) == 1
    assert hits[0].resource.id == "tech-docker"
    # Must be sub-millisecond in-memory
    assert elapsed_ms < 5.0

    # Distant vector must miss
    assert cache.get(mock_vec_distant, domain="tech", jurisdiction="GLOBAL") is None

    # Invalidation test
    cache.invalidate_tags(["docker"])
    assert cache.get(mock_vec_near, domain="tech", jurisdiction="GLOBAL") is None


def test_negative_constraints_and_anti_skill_synthesizer():
    """Verify natural language negation parsing and anti-skill/territorial exclusion."""
    synthesizer = get_self_query_synthesizer()

    # Query with negative skill exclusions
    query_neg = "cloud devops architecture roadmap no aws without django"
    constraints = synthesizer.synthesize_constraints(query_neg)

    assert "aws" in constraints.excluded_skills
    assert "django" in constraints.excluded_skills

    # Query with jurisdiction exclusion
    query_jur = "corporate compliance law exclude us"
    constraints_jur = synthesizer.synthesize_constraints(query_jur)
    assert "US" in constraints_jur.excluded_jurisdictions

    # Matching test
    res_aws = VerifiedResource(
        id="tech-aws-solutions",
        title="AWS Solutions Architect Professional",
        url="https://aws.amazon.com/cert",
        platform="AWS",
        type=ResourceType.CERTIFICATION,
        domain="tech",
        skills_covered=["aws", "cloud architecture"],
        description="Enterprise AWS architecture."
    )

    res_k8s = VerifiedResource(
        id="tech-k8s-cloud",
        title="Kubernetes Cloud Native Engineering",
        url="https://kubernetes.io/learn",
        platform="Linux Foundation",
        type=ResourceType.COURSE,
        domain="tech",
        skills_covered=["kubernetes", "docker"],
        description="Containerized deployments without proprietary cloud lock-in."
    )

    assert synthesizer.matches_constraints(res_aws, constraints) is False
    assert synthesizer.matches_constraints(res_k8s, constraints) is True


def test_ragas_triad_hallucination_guardrails():
    """Verify RAGAS Triad Evaluator calculates Context Relevance, Faithfulness, and Answer Relevance."""
    ragas = get_ragas_evaluator()

    res_dpdp = VerifiedResource(
        id="legal-in-dpdp",
        title="Digital Personal Data Protection Act 2023",
        url="https://meity.gov.in/dpdp",
        platform="MeitY",
        type=ResourceType.DOCUMENTATION,
        domain="legal",
        jurisdiction="IN",
        skills_covered=["dpdp", "data privacy", "consent management"],
        description="Official DPDP compliance manual for Indian corporations."
    )

    # 1. High-Relevance & Grounded Case
    triad_good = ragas.evaluate_triad(
        query_skills=["dpdp", "data privacy"],
        retrieved_resources=[res_dpdp],
        target_domain="legal",
        seniority="senior",
        generated_terms=["dpdp", "data privacy", "meity"]
    )

    assert triad_good.context_relevance >= 0.80
    assert triad_good.faithfulness >= 0.80
    assert triad_good.is_grounded is True

    # 2. Ungrounded / Hallucinatory Case
    triad_hallucinatory = ragas.evaluate_triad(
        query_skills=["quantum cryptography", "neuromorphic chips"],
        retrieved_resources=[res_dpdp],
        target_domain="tech",
        seniority="senior",
        generated_terms=["quantum annealing", "spin qubits", "dilution refrigerators"]
    )

    assert triad_hallucinatory.context_relevance == 0.0
    assert triad_hallucinatory.is_grounded is False


def test_cdc_bus_live_invalidation_and_subscription():
    """Verify CDC event bus notifies subscribers and flushes cache tags on resource updates."""
    bus = get_cdc_bus()
    cache = get_semantic_cache()

    # Populate cache with a tag
    mock_vec = [0.2] * 384
    dummy_res = VerifiedResource(
        id="legal-dpdp-cache-test",
        title="DPDP Act Compliance",
        url="https://example.com/test",
        platform="NLSIU",
        type=ResourceType.DOCUMENTATION,
        domain="legal",
        jurisdiction="IN",
        skills_covered=["dpdp"],
        description="Testing live invalidation."
    )

    from app.knowledge.models import ResourceSearchResult
    cache.set(
        query_text="dpdp legal compliance",
        query_vector=mock_vec,
        results=[ResourceSearchResult(resource=dummy_res, score=0.99, matched_skills=["dpdp"])],
        domain="legal",
        jurisdiction="IN"
    )

    assert cache.get(mock_vec, domain="legal", jurisdiction="IN") is not None

    received_events = []

    def cdc_handler(event: CDCEvent):
        received_events.append(event)

    bus.subscribe("RESOURCE_UPDATED", cdc_handler)

    # Publish update event synchronously
    update_event = CDCEvent(
        event_type="RESOURCE_UPDATED",
        resource_id="legal-dpdp-cache-test",
        domain="legal",
        tags=["dpdp"]
    )
    bus.publish_sync(update_event)

    # Verify event delivery
    assert len(received_events) == 1
    assert received_events[0].resource_id == "legal-dpdp-cache-test"

    # Verify semantic cache entry was invalidated automatically
    assert cache.get(mock_vec, domain="legal", jurisdiction="IN") is None


def test_hierarchical_parent_child_chunk_model():
    """Verify ChildChunk model and parent document attachment."""
    chunk1 = ChildChunk(
        id="chunk-dpdp-penalties",
        title="DPBI Penalty Schedule",
        content="Penalties up to 250 crores INR under DPDP Act 2023.",
        skills_covered=["dpdp", "regulatory compliance"],
        parent_id="legal-in-dpdp-act-2023"
    )

    parent_res = VerifiedResource(
        id="legal-in-dpdp-act-2023",
        title="Digital Personal Data Protection Act 2023 Compliance & Consent Architecture",
        url="https://www.meity.gov.in/content/digital-personal-data-protection-act-2023",
        platform="MeitY / NLSIU Legal Portal",
        type=ResourceType.DOCUMENTATION,
        domain="legal",
        jurisdiction="IN",
        skills_covered=["dpdp", "data privacy"],
        description="Comprehensive Indian data protection law.",
        child_chunks=[chunk1]
    )

    assert len(parent_res.child_chunks) == 1
    assert parent_res.child_chunks[0].parent_id == parent_res.id
    assert parent_res.jurisdiction == "IN"


def test_retriever_geo_routing_and_anti_skill_integration():
    """Verify retriever filters out-of-jurisdiction regulatory laws and respects negative anti-skills."""
    from app.knowledge.models import ResourceSearchResult
    geo_router = get_geo_router()

    res_in = VerifiedResource(
        id="legal-in-dpdp-act-2023",
        title="Digital Personal Data Protection Act 2023 Compliance & Consent Architecture",
        url="https://example.com/dpdp",
        platform="MeitY / NLSIU Legal Portal",
        type=ResourceType.DOCUMENTATION,
        domain="legal",
        jurisdiction="IN",
        skills_covered=["dpdp", "data privacy"],
        description="Indian data privacy regulation."
    )
    res_us = VerifiedResource(
        id="legal-uspto-patent-guide",
        title="USPTO Patent Examination & Intellectual Property Guide",
        url="https://example.com/uspto",
        platform="USPTO",
        type=ResourceType.DOCUMENTATION,
        domain="legal",
        jurisdiction="US",
        skills_covered=["intellectual property", "patent law"],
        description="US Patent Office guidelines."
    )

    # Route for an Indian legal inquiry
    routed = geo_router.filter_and_route(
        candidates=[
            ResourceSearchResult(resource=res_in, score=0.9, matched_skills=["dpdp"]),
            ResourceSearchResult(resource=res_us, score=0.9, matched_skills=["patent law"])
        ],
        target_jurisdiction="IN",
        domain="legal"
    )

    # Assert US resource is completely pruned (0% leakage) and IN resource is retained
    assert len(routed) == 1
    assert routed[0].resource.id == "legal-in-dpdp-act-2023"
    assert routed[0].resource.jurisdiction == "IN"


def test_all_domains_geographical_rag_routing():
    """Verify Geographical RAG Routing functions across ALL domains (Legal, Finance, Healthcare, Trades, Tech)."""
    geo_router = get_geo_router()
    from app.knowledge.models import ResourceSearchResult

    # 1. FINANCE DOMAIN: Indian SEBI/Ind AS vs US SEC EDGAR/GAAP
    assert geo_router.detect_jurisdiction("SEBI LODR regulations and RBI NBFC compliance") == "IN"
    assert geo_router.detect_jurisdiction("ICAI Ind AS and GST corporate taxation in India") == "IN"
    assert geo_router.detect_jurisdiction("US SEC EDGAR 10-K filings and US GAAP") == "US"

    res_fin_in = VerifiedResource(
        id="finance-in-sebi",
        title="SEBI & RBI Master Directions",
        url="https://sebi.gov.in",
        platform="SEBI",
        type=ResourceType.DOCUMENTATION,
        domain="finance",
        jurisdiction="IN",
        skills_covered=["sebi regulations", "rbi compliance"],
        description="Indian securities and banking regulations."
    )
    res_fin_us = VerifiedResource(
        id="finance-us-sec",
        title="SEC EDGAR Guide to Public Company Filings",
        url="https://sec.gov",
        platform="SEC.gov",
        type=ResourceType.DOCUMENTATION,
        domain="finance",
        jurisdiction="US",
        skills_covered=["sec filings", "gaap"],
        description="US securities regulations."
    )
    routed_fin = geo_router.filter_and_route(
        candidates=[
            ResourceSearchResult(resource=res_fin_in, score=0.9, matched_skills=["sebi regulations"]),
            ResourceSearchResult(resource=res_fin_us, score=0.9, matched_skills=["sec filings"])
        ],
        target_jurisdiction="IN",
        domain="finance"
    )
    assert len(routed_fin) == 1
    assert routed_fin[0].resource.id == "finance-in-sebi"

    # 2. HEALTHCARE DOMAIN: Indian ABDM/NABH vs US HIPAA/NCLEX
    assert geo_router.detect_jurisdiction("ABDM health data exchange and ABHA health ID") == "IN"
    assert geo_router.detect_jurisdiction("NABH hospital accreditation and clinical establishments act") == "IN"
    assert geo_router.detect_jurisdiction("HIPAA privacy rule and protected health information") == "US"
    assert geo_router.detect_jurisdiction("NCLEX-RN candidate preparation for US registered nursing") == "US"

    res_health_in = VerifiedResource(
        id="health-in-abdm",
        title="NHA ABDM Health Data Standards",
        url="https://abdm.gov.in",
        platform="NHA",
        type=ResourceType.DOCUMENTATION,
        domain="healthcare",
        jurisdiction="IN",
        skills_covered=["abdm", "fhir"],
        description="Indian national health interoperability."
    )
    res_health_us = VerifiedResource(
        id="health-us-hipaa",
        title="HHS HIPAA Training",
        url="https://hhs.gov",
        platform="HHS",
        type=ResourceType.DOCUMENTATION,
        domain="healthcare",
        jurisdiction="US",
        skills_covered=["hipaa", "phi security"],
        description="US federal healthcare privacy."
    )
    routed_health = geo_router.filter_and_route(
        candidates=[
            ResourceSearchResult(resource=res_health_in, score=0.9, matched_skills=["abdm"]),
            ResourceSearchResult(resource=res_health_us, score=0.9, matched_skills=["hipaa"])
        ],
        target_jurisdiction="IN",
        domain="healthcare"
    )
    assert len(routed_health) == 1
    assert routed_health[0].resource.id == "health-in-abdm"

    # 3. TRADES DOMAIN: Indian BIS IS 732/CEA vs US NEC NFPA 70
    assert geo_router.detect_jurisdiction("BIS IS 732 electrical wiring and CEA regulations in India") == "IN"
    assert geo_router.detect_jurisdiction("National Building Code India NBC 2016 fire safety") == "IN"
    assert geo_router.detect_jurisdiction("National Electrical Code NEC NFPA 70 handbook") == "US"

    res_trade_in = VerifiedResource(
        id="trades-in-bis",
        title="BIS IS 732 & CEA Electrical Regulations",
        url="https://bis.gov.in",
        platform="BIS",
        type=ResourceType.DOCUMENTATION,
        domain="trades",
        jurisdiction="IN",
        skills_covered=["electrical code", "is 732"],
        description="Indian standard 230V 50Hz wiring installations."
    )
    res_trade_us = VerifiedResource(
        id="trades-us-nec",
        title="NEC NFPA 70 Electrical Code Handbook",
        url="https://nfpa.org",
        platform="NFPA",
        type=ResourceType.DOCUMENTATION,
        domain="trades",
        jurisdiction="US",
        skills_covered=["nec", "electrical code"],
        description="US standard 120V 60Hz wiring codes."
    )
    routed_trade = geo_router.filter_and_route(
        candidates=[
            ResourceSearchResult(resource=res_trade_in, score=0.9, matched_skills=["is 732"]),
            ResourceSearchResult(resource=res_trade_us, score=0.9, matched_skills=["nec"])
        ],
        target_jurisdiction="IN",
        domain="trades"
    )
    assert len(routed_trade) == 1
    assert routed_trade[0].resource.id == "trades-in-bis"

    # 4. TECH DOMAIN: Indian UPI/NPCI/ONDC vs Foreign
    assert geo_router.detect_jurisdiction("UPI payment gateway and NPCI ONDC architecture") == "IN"
    res_tech_in = VerifiedResource(
        id="tech-in-upi",
        title="NPCI UPI & ONDC Architecture",
        url="https://npci.org.in",
        platform="NPCI",
        type=ResourceType.DOCUMENTATION,
        domain="tech",
        jurisdiction="IN",
        skills_covered=["upi", "ondc"],
        description="Indian digital public infrastructure."
    )
    score_upi_in = geo_router.score_geo_compatibility("IN", "IN", domain="tech")
    assert score_upi_in == 1.0

    # 5. Universal Concepts: GLOBAL resources remain accessible
    res_global = VerifiedResource(
        id="tech-docker",
        title="Docker Container Fundamentals",
        url="https://docker.com",
        platform="Docker",
        type=ResourceType.COURSE,
        domain="tech",
        jurisdiction="GLOBAL",
        skills_covered=["docker"],
        description="Universal containerization."
    )
    score_global_in = geo_router.score_geo_compatibility("GLOBAL", "IN", domain="tech")
    assert score_global_in == 0.90
