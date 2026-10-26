import pytest
import socket
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from datetime import datetime



@pytest.mark.asyncio
async def test_health_check(llm_tracker):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data
        assert llm_tracker.call_count == 0

@pytest.mark.asyncio
async def test_analyze_endpoint(llm_tracker):
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
        # Exactly 3 Phase 3 calls: executive_summary, ats_optimization, seniority_alignment
        # (experience extraction matches regex; roadmap skipped for perfect match)
        assert llm_tracker.call_count == 3

@pytest.mark.asyncio
async def test_analyze_endpoint_unparseable_jd(llm_tracker):
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
        assert data["scoreBreakdown"]["skillsMatch"] is None
        assert data["scoreBreakdown"]["seniorityMatch"] is None
        assert data["scoreBreakdown"]["domainMatch"] is None
        assert data.get("seniorityAnalysis") is None
        assert data.get("seniorityAssessed") is None
        assert data.get("seniorityReason") is None
        assert data.get("seniorityStatus") is None
        # Exits early at Phase 1, zero LLM calls made
        assert llm_tracker.call_count == 0

@pytest.mark.asyncio
async def test_analyze_endpoint_unconfirmed_seniority_skips_llm(llm_tracker):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Candidate has skills but no stated years (date ranges only, unconfirmed)
        request_data = {
            "resume": "Software engineer building services in Python, SQL, and Docker. Experience: 2018 - 2023 Acme Corp.",
            "jdText": "Looking for a Software engineer with 4 years experience in Python, SQL, and Docker."
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["seniorityAssessed"] is False
        assert data["seniorityStatus"] == "unconfirmed"
        assert data["scoreBreakdown"]["seniorityMatch"] is None
        assert data["scoreBreakdown"]["skillsMatch"] == 100
        # When seniority is unconfirmed, overall score renormalizes to skills-only (100)
        assert data["overallScore"] == 100
        # seniority_alignment LLM call is skipped! Exactly 3 calls: 1 candidate extraction fallback + 2 Phase 3 calls (executive_summary, ats_optimization)
        assert llm_tracker.call_count == 3
        assert not any("alignment_summary" in call["schema"] for call in llm_tracker.calls)

@pytest.mark.asyncio
async def test_analyze_validation_error(llm_tracker):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_data = {
            "resume": "Short"  # Too short
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 422
        assert llm_tracker.call_count == 0

@pytest.mark.asyncio
async def test_analyze_missing_jd(llm_tracker):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_data = {
            "resume": "A" * 100
            # No jd_text or jd_url
        }
        response = await client.post("/api/v1/analyze", json=request_data)
        assert response.status_code == 422
        assert llm_tracker.call_count == 0
