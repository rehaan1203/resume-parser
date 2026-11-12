"""Unit tests for Direction 2: Interview Intelligence with STAR Model Rubrics."""
import pytest
from app.knowledge.retriever import get_retriever
from app.knowledge.models import InterviewGuideItem


def test_interview_guide_retrieval_for_legal_contracts():
    """Verify retriever surfaces contract drafting interview guide with rubric and STAR answer."""
    retriever = get_retriever()
    guides = retriever.get_interview_guides_for_skills(
        skills=["contract drafting", "negotiation"],
        domain="legal",
        limit=2
    )
    assert len(guides) > 0
    g = guides[0]
    assert isinstance(g, InterviewGuideItem)
    assert "commercial negotiations" in g.question.lower() or "liability" in g.question.lower()
    assert len(g.evaluation_criteria) >= 2
    assert "indemnif" in g.star_model_answer.situation.lower() or "liability" in g.star_model_answer.situation.lower()
    assert g.star_model_answer.action is not None
    assert g.star_model_answer.result is not None


def test_interview_guide_retrieval_for_kubernetes():
    """Verify retriever surfaces kubernetes incident diagnosis interview guide."""
    retriever = get_retriever()
    guides = retriever.get_interview_guides_for_skills(
        skills=["kubernetes", "docker"],
        domain="tech",
        limit=2
    )
    assert len(guides) > 0
    k_guide = guides[0]
    assert "crash" in k_guide.question.lower() or "pod" in k_guide.star_model_answer.situation.lower()
    assert any("kubectl" in c.lower() or "oomkilled" in c.lower() for c in k_guide.evaluation_criteria)
