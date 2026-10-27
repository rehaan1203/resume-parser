import pytest
from unittest.mock import AsyncMock, patch
from app.ai.explainer import Phase3Explainer
from app.ai.orchestrator import DeterministicOrchestrator

@pytest.mark.asyncio
async def test_explainer_tracks_degraded_sections_on_exception():
    """Phase3Explainer records failed sections in self.degraded_sections."""
    explainer = Phase3Explainer()
    # Force LLM call to raise Exception
    explainer.client.generate_structured_content = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    
    summary = await explainer.generate_executive_summary(75, ["Python"], ["Docker"], 0)
    assert "Candidate achieved a 75% match" in summary
    assert "executive_summary" in explainer.degraded_sections

    ats = await explainer.generate_ats_optimization(["Docker"], "Job description")
    assert "keywords" in ats
    assert "ats_optimization" in explainer.degraded_sections

    roadmap = await explainer.generate_roadmap(["Docker"])
    assert "Fallback Roadmap" in roadmap.get("title", "")
    assert "roadmap" in explainer.degraded_sections

    alignment = await explainer.generate_seniority_alignment(3, 5, "Mid", "Senior", 2)
    assert alignment.get("gap") == 2
    assert "seniority_alignment" in explainer.degraded_sections

@pytest.mark.asyncio
async def test_orchestrator_includes_degraded_sections():
    """DeterministicOrchestrator includes degraded_sections in its response."""
    orchestrator = DeterministicOrchestrator()
    # Stub Phase3Explainer to simulate degraded sections
    with patch("app.ai.explainer.Phase3Explainer") as MockExplainer:
        mock_instance = MockExplainer.return_value
        mock_instance.degraded_sections = ["executive_summary", "roadmap"]
        mock_instance.generate_executive_summary = AsyncMock(return_value="Degraded summary")
        mock_instance.generate_ats_optimization = AsyncMock(return_value={"keywords": []})
        mock_instance.generate_seniority_alignment = AsyncMock(return_value={})
        mock_instance.generate_roadmap = AsyncMock(return_value={"weeks": []})
        
        result = await orchestrator.process({
            "resume": "Software engineer with 5 years experience in Python and SQL.",
            "jd_text": "Looking for engineer with Python, SQL, and Docker. 5 years required."
        })
        assert "degraded_sections" in result
        assert result["degraded_sections"] == ["executive_summary", "roadmap"]
