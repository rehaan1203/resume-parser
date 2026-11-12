"""Unit tests for Direction 1: Career Transition Knowledge Base."""
import pytest
from app.knowledge.retriever import get_retriever
from app.knowledge.models import TransitionBridge


def test_transition_bridge_retrieval_healthcare_to_tech():
    """Verify healthcare -> tech transition bridge returns verified strengths and certs."""
    retriever = get_retriever()
    bridge = retriever.get_transition_bridge("healthcare", "tech")
    
    assert bridge is not None
    assert isinstance(bridge, TransitionBridge)
    assert bridge.source_domain == "healthcare"
    assert bridge.target_domain == "tech"
    assert any("EHR" in s or "HIPAA" in s for s in bridge.transferable_strengths)
    assert any("AWS" in c or "CAHIMS" in c for c in bridge.bridge_certifications)
    assert "triage" in bridge.strategic_advice.lower()


def test_transition_bridge_retrieval_legal_to_tech():
    """Verify legal -> tech transition bridge returns governance credentials."""
    retriever = get_retriever()
    bridge = retriever.get_transition_bridge("legal", "tech")
    
    assert bridge is not None
    assert any("IAPP" in c or "Cybersecurity" in c for c in bridge.bridge_certifications)
    assert "statutory" in bridge.transferable_strengths[0].lower() or "contract" in bridge.strategic_advice.lower()


def test_transition_bridge_nonexistent_returns_none():
    """Verify unknown transitions return None gracefully without throwing errors."""
    retriever = get_retriever()
    bridge = retriever.get_transition_bridge("culinary", "aerospace")
    assert bridge is None

