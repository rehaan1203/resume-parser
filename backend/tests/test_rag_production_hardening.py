"""Unit tests verifying production hardening of the RAG subsystem."""
import pytest
from app.knowledge.retriever import get_retriever
from app.knowledge.embedding_service import EmbeddingService
from app.prompts.roadmap_prompt import build_rag_upskill_roadmap_prompt
from app.prompts.ats_prompt import build_rag_ats_prompt


def test_eager_warmup_and_indexing():
    """Verify that get_retriever initializes and indexes catalogs with zero delay."""
    import asyncio
    async def _run():
        retriever = get_retriever()
        count = await retriever.initialize_and_index_catalogs()
        assert count >= 28
        assert retriever._is_indexed is True
    asyncio.run(_run())


def test_domain_strictness_filter():
    """Verify retriever strictly prioritizes matching target domain and prevents domain bleed."""
    import asyncio
    async def _run():
        retriever = get_retriever()
        # Query skill 'compliance' under 'legal' domain
        legal_res = await retriever.retrieve_for_skill(skill="compliance", domain="legal", top_k=2)
        assert len(legal_res) > 0
        for r in legal_res:
            assert r.resource.domain == "legal"

        # Query skill 'compliance' under 'healthcare' domain
        health_res = await retriever.retrieve_for_skill(skill="compliance", domain="healthcare", top_k=2)
        assert len(health_res) > 0
        for r in health_res:
            assert r.resource.domain == "healthcare"
    asyncio.run(_run())


def test_compact_prompt_budget_protection():
    """Verify prompt builders enforce character limits to prevent LLM context overflow."""
    long_desc = "A" * 500
    dummy_resources = [
        {"title": f"Resource {i}", "url": f"https://sample.org/{i}", "type": "course", "description": long_desc}
        for i in range(10)
    ]
    prompt = build_rag_upskill_roadmap_prompt(
        gaps=["kubernetes", "docker"],
        gap_type="standard_upskill",
        verified_resources=dummy_resources
    )
    # Ensure capped to 8 resources and truncated descriptions
    assert "Resource 0" in prompt
    assert "Resource 7" in prompt
    assert "Resource 8" not in prompt  # Capped at top 8
    assert "AAAA..." in prompt  # Truncated description

