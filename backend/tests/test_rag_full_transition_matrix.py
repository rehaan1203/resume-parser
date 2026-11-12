"""Unit tests verifying the full 20-pair bidirectional career transition matrix."""
import pytest
from app.knowledge.retriever import get_retriever
from app.knowledge.models import TransitionBridge

DOMAINS = ["tech", "legal", "healthcare", "trades", "finance"]


def test_full_20_pair_transition_matrix_coverage():
    """Verify that every single directed pair (A -> B) across all 5 domains exists and is fully populated."""
    retriever = get_retriever()
    pairs_tested = 0

    for source in DOMAINS:
        for target in DOMAINS:
            if source == target:
                continue
            
            bridge = retriever.get_transition_bridge(source, target)
            assert bridge is not None, f"Missing transition bridge for {source} -> {target}"
            assert isinstance(bridge, TransitionBridge)
            assert bridge.source_domain == source
            assert bridge.target_domain == target
            
            # Content depth asserts: ensure no empty or shallow placeholder entries
            assert len(bridge.transferable_strengths) >= 3, f"Insufficient strengths for {source} -> {target}"
            assert len(bridge.bridge_certifications) >= 2, f"Insufficient certifications for {source} -> {target}"
            assert len(bridge.strategic_advice) > 40, f"Advice too short for {source} -> {target}"
            assert len(bridge.recommended_projects) >= 2, f"Insufficient projects for {source} -> {target}"
            
            pairs_tested += 1

    assert pairs_tested == 20, f"Expected 20 directed transition pairs, but tested {pairs_tested}"


def test_domain_alias_normalization():
    """Verify that aliases like 'technology', 'medical', 'law' resolve to canonical transition bridges."""
    retriever = get_retriever()
    
    # technology -> law (tech -> legal)
    bridge1 = retriever.get_transition_bridge("technology", "law")
    assert bridge1 is not None
    assert bridge1.id == "bridge-tech-to-legal"
    assert any("Patent" in c for c in bridge1.bridge_certifications)

    # medical -> software (healthcare -> tech)
    bridge2 = retriever.get_transition_bridge("medical", "software")
    assert bridge2 is not None
    assert bridge2.id == "bridge-healthcare-to-tech"

    # accounting -> skilled_trades (finance -> trades)
    bridge3 = retriever.get_transition_bridge("accounting", "skilled_trades")
    assert bridge3 is not None
    assert bridge3.id == "bridge-finance-to-trades"

