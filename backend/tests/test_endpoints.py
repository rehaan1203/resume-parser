import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from datetime import datetime

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
            "resume": "A" * 100,
            "jdText": "B" * 100
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
