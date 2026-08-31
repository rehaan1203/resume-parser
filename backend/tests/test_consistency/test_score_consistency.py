"""Test score consistency across multiple runs."""
import pytest
from app.core.agents.multi_agent_orchestrator import MultiAgentOrchestrator

@pytest.mark.asyncio
async def test_score_consistency():
    """Test that scores are consistent across multiple runs."""
    orchestrator = MultiAgentOrchestrator()

    # Use the same inputs for all runs
    resume = """SARAH WILLIAMS
    Lawyer with 2 years of experience in legal research, contract review, litigation support...
    """
    jd = """TECHNOLOGY LAWYER
    Experience: 3+ Years
    We are looking for an experienced Technology Lawyer...
    """

    scores = []
    for i in range(5):
        result = await orchestrator.analyze(resume, jd)
        scores.append(result["overall_score"])
        print(f"Run {i+1}: {scores[-1]}%")

    # Check variance
    variance = max(scores) - min(scores)
    print(f"Variance: {variance}%")

    # Assert variance is within acceptable range
    assert variance <= 15, f"Score variance too high: {variance}%"
