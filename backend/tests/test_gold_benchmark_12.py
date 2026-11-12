"""Hermetic benchmark runner verifying the 12 Gold Benchmark Pairs (D4)."""
import json
import os
import pytest
from app.ai.open_domain_extractor import OpenDomainExtractor

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "gold_set_12_pairs.json")

def load_gold_set():
    if not os.path.exists(FIXTURE_PATH):
        pytest.skip(f"Gold benchmark fixture not found at {FIXTURE_PATH}")
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("pairs", [])

@pytest.mark.asyncio
async def test_gold_set_extraction_coverage():
    """Verify that all 12 benchmark pairs extract recognizable requirements without crashing."""
    pairs = load_gold_set()
    assert len(pairs) == 12

    extractor = OpenDomainExtractor()
    for pair in pairs:
        pair_id = pair.get("pair_id")
        domain = pair.get("domain")
        jd = pair.get("jd", "") or pair.get("jd_text", "")
        resume = pair.get("resume", "") or pair.get("resume_text", "")

        # 1. Extract requirements
        reqs = await extractor.extract_requirements(jd)
        assert len(reqs) >= 1, f"Pair {pair_id} ({domain}) extracted 0 requirements"

        # 2. Evaluate matches
        result = await extractor.evaluate_matches(reqs, resume)
        assert result.weighted_score >= 0.0
        assert isinstance(result.skill_gaps, list)
        assert isinstance(result.strengths, list)

@pytest.mark.asyncio
async def test_gold_set_multidomain_coverage():
    """Ensure all 4 core domains (Healthcare, Trades, Legal, Tech) are covered in the gold set."""
    pairs = load_gold_set()
    all_domains_str = " ".join(p.get("domain", "").lower() for p in pairs)
    assert "healthcare" in all_domains_str or "nursing" in all_domains_str
    assert "trades" in all_domains_str or "hvac" in all_domains_str
    assert "law" in all_domains_str or "legal" in all_domains_str
    assert "systems" in all_domains_str or "data" in all_domains_str
