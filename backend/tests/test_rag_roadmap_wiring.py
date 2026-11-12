"""Tests for RAG Knowledge Base retriever wiring into Roadmap generation."""
import pytest
from app.prompts.roadmap_prompt import build_rag_upskill_roadmap_prompt, build_upskill_roadmap_prompt
from app.knowledge.retriever import get_retriever


def test_build_rag_upskill_roadmap_prompt_structure():
    """Verify build_rag_upskill_roadmap_prompt formats verified resources and strict instructions."""
    verified_resources = [
        {
            "title": "Contract Law Basics",
            "url": "https://coursera.org/learn/contract-law",
            "resource_type": "course",
            "description": "Foundational course on contract formation and breach remedies."
        },
        {
            "title": "Tech Transaction Playbook",
            "url": "https://sample.org/tech-playbook",
            "resource_type": "doc",
            "description": "Standard clauses for software licensing and data protection."
        }
    ]
    prompt = build_rag_upskill_roadmap_prompt(
        gaps=["contract drafting", "intellectual property"],
        gap_type="short_upskill",
        verified_resources=verified_resources
    )
    
    assert "contract drafting" in prompt
    assert "https://coursera.org/learn/contract-law" in prompt
    assert "https://sample.org/tech-playbook" in prompt
    assert "VERIFIED LEARNING RESOURCES AVAILABLE" in prompt
    assert "MANDATORY URL USAGE INSTRUCTIONS" in prompt
    assert "DO NOT hallucinate fake or placeholder URLs" in prompt


def test_build_rag_upskill_roadmap_prompt_empty_resources():
    """Verify build_rag_upskill_roadmap_prompt falls back cleanly when no resources provided."""
    prompt = build_rag_upskill_roadmap_prompt(
        gaps=["python"],
        gap_type="mini_upskill",
        verified_resources=[]
    )
    assert "python" in prompt
    assert "None provided" in prompt
    assert "VERIFIED LEARNING RESOURCES AVAILABLE" in prompt


def test_retriever_query_for_legal_gaps():
    """Verify that retriever returns verified legal resources for legal skills."""
    import asyncio
    async def _run():
        retriever = get_retriever()
        results = await retriever.search_for_gaps(
            skills=["contract drafting", "compliance"],
            domain="legal",
            limit=5
        )
        assert len(results) > 0
        urls = [r.url for r in results]
        assert any("coursera.org" in u or "eff.org" in u or "law" in u.lower() for u in urls)
    asyncio.run(_run())
