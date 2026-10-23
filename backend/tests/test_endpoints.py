import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from datetime import datetime

@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    """Hermetic test fixture mocking all external network, AI, and cache services."""
    from app.config import settings
    monkeypatch.setattr(settings, "google_api_key", settings.google_api_key or "mock-google-key")
    monkeypatch.setattr(settings, "mistral_api_key", settings.mistral_api_key or "mock-mistral-key")
    monkeypatch.setattr(settings, "tavily_api_key", settings.tavily_api_key or "mock-tavily-key")
    monkeypatch.setattr(settings, "cache_enabled", False)

    with patch("app.utils.link_processor.LinkProcessor.process_response", new_callable=AsyncMock) as mock_links, \
         patch("app.ai.explainer.Phase3Explainer.generate_executive_summary", new_callable=AsyncMock) as mock_exec, \
         patch("app.ai.explainer.Phase3Explainer.generate_ats_optimization", new_callable=AsyncMock) as mock_ats, \
         patch("app.ai.explainer.Phase3Explainer.generate_seniority_alignment", new_callable=AsyncMock) as mock_sen, \
         patch("app.ai.explainer.Phase3Explainer.generate_roadmap", new_callable=AsyncMock) as mock_rd, \
         patch("app.ai.explainer.Phase3Explainer.generate_mismatch_message", new_callable=AsyncMock) as mock_mismatch, \
         patch("app.ai.client.GenAIClient.generate_content", new_callable=AsyncMock) as mock_gen_content, \
         patch("app.ai.client.GenAIClient.generate_structured_content", new_callable=AsyncMock) as mock_gen_structured, \
         patch("app.utils.redis_client.RedisClient.ping", new_callable=AsyncMock) as mock_redis_ping, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        
        mock_links.side_effect = lambda resp: resp
        mock_exec.return_value = "Candidate shows strong alignment with the technical requirements."
        mock_ats.return_value = {
            "keywords": ["Python", "SQL", "Docker"],
            "phrasing": [],
            "formatting_tips": ["Use standard formatting"]
        }
        mock_sen.return_value = {
            "alignment_summary": "Meets required seniority level.",
            "advice": "Seniority matches requirements."
        }
        mock_rd.return_value = {
            "type": "standard_upskill",
            "title": "Learning Roadmap",
            "weeks": []
        }
        mock_mismatch.return_value = "Domain mismatch detected."
        mock_gen_content.return_value = "{}"
        mock_gen_structured.return_value = {}
        mock_redis_ping.return_value = False
        
        yield

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data

@pytest.mark.asyncio
async def test_analyze_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_data = {
            "resume": "Software engineer with 4 years experience in Python, SQL, and Docker building services.",
            "jdText": "Looking for a Software engineer with 4 years experience in Python, SQL, and Docker."
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["id"].startswith("ai-")
        assert 0 <= data["overallScore"] <= 100
        assert "frictionPoints" in data
        assert "skillGaps" in data
        assert "strengths" in data
        assert "roadmap" in data

@pytest.mark.asyncio
async def test_analyze_endpoint_unparseable_jd():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_data = {
            "resume": "Experienced logistics coordinator with 5 years experience in regional routing.",
            "jdText": "Hiring a logistics coordinator with 5 years experience in operations and dispatch."
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["id"].startswith("ai-")
        assert data["status"] == "unparseable_jd"
        assert data["overallScore"] is None
        assert data["skillsDetected"] == 0
        assert data["lowConfidence"] is True

@pytest.mark.asyncio
async def test_analyze_validation_error():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_data = {
            "resume": "Short"  # Too short
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_analyze_missing_jd():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_data = {
            "resume": "A" * 100
            # No jd_text or jd_url
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 422
