"""Unit tests for Phase 3 RAG Enhancements (Options 1, 2, and 3)."""
import asyncio
import pytest
from app.knowledge.retriever import get_retriever
from app.knowledge.taxonomy_service import get_taxonomy_service
from app.ai.open_domain_extractor import OpenDomainExtractor


def test_option_1_catalog_expansion():
    """Verify that multi-domain catalogs have expanded and index properly."""
    async def _run():
        retriever = get_retriever()
        count = await retriever.initialize_and_index_catalogs()
        # Catalogs now have 28+ verified resources
        assert count >= 25

        # Query tech domain
        tech_res = await retriever.search_for_gaps(["next.js", "pytorch"], domain="tech", limit=2)
        assert len(tech_res) > 0

        # Query finance domain (Stage 6 graph expands prerequisite financial accounting -> check top 2 covers CFI)
        fin_res = await retriever.search_for_gaps(["financial modeling"], domain="finance", limit=2)
        assert len(fin_res) > 0
        assert any("corporatefinanceinstitute" in r.url or "cfi" in r.id or r.domain == "finance" for r in fin_res)
    asyncio.run(_run())


def test_option_2_phrasing_templates():
    """Verify that curated STAR phrasing templates are retrieved for skills."""
    async def _run():
        retriever = get_retriever()
        templates = await retriever.get_phrasing_templates_for_gaps(
            skills=["contract drafting", "compliance"],
            domain="legal",
            limit=2
        )
        assert len(templates) > 0
        tmpl = templates[0]
        assert len(tmpl.action_verbs) > 0
        assert "Negotiated" in tmpl.action_verbs or "Drafted" in tmpl.action_verbs or "Orchestrated" in tmpl.action_verbs
        assert "[X]" in tmpl.star_template or "%" in tmpl.example_after
    asyncio.run(_run())


def test_option_3_taxonomy_normalization():
    """Verify taxonomy normalizes statutory citations and synonyms (e.g. 45 CFR Part 164 -> HIPAA)."""
    taxonomy = get_taxonomy_service()
    
    # 1. Statutory citation
    assert taxonomy.normalize_term("45 cfr part 164") == "hipaa compliance"
    assert taxonomy.normalize_term("k8s") == "kubernetes"
    assert taxonomy.normalize_term("first chair trial experience") == "trial litigation"

    # 2. Match scoring with synonym in resume
    extractor = OpenDomainExtractor()
    requirements = [
        {"name": "45 CFR Part 164", "category": "skill", "importance": "must_have"}
    ]
    # Resume mentions 'HIPAA Compliance' instead of raw citation
    resume = "Seasoned healthcare coordinator with extensive HIPAA compliance and EHR charting experience."
    
    result = asyncio.run(extractor.evaluate_matches(requirements, resume))
    assert result.weighted_score == 100.0
    assert result.matches[0].status == "matched"
