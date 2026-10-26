import pytest
import socket
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from datetime import datetime

class LLMCallTracker:
    def __init__(self):
        self.call_count = 0
        self.calls = []

    async def generate_structured_content(self, prompt, output_schema, model=None, temperature=None):
        self.call_count += 1
        self.calls.append({"prompt": prompt, "schema": output_schema, "model": model})
        if "summary" in output_schema:
            return {"summary": "Candidate shows strong alignment with the technical requirements."}
        if "keywords" in output_schema:
            return {
                "keywords": ["Python", "SQL", "Docker"],
                "phrasing": [],
                "formatting_tips": ["Use standard formatting"]
            }
        if "alignment_summary" in output_schema:
            return {
                "alignment_summary": "Meets required seniority level.",
                "advice": "Seniority matches requirements."
            }
        if "weeks" in output_schema:
            return {
                "type": "standard_upskill",
                "title": "Learning Roadmap",
                "weeks": []
            }
        if "message" in output_schema:
            return {"message": "Domain mismatch detected."}
        if "years" in output_schema:
            if "status" in output_schema:
                return {"status": "found", "years": 4, "evidence_quote": "4 years experience"}
            return {"years": 4}
        if "status" in output_schema:
            return {"status": "not_found", "years": None, "evidence_quote": None}
        return {}

@pytest.fixture
def llm_tracker():
    return LLMCallTracker()

@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch, llm_tracker):
    """Hermetic test fixture blocking real external sockets, stubbing AI calls, and isolating services."""
    from app.config import settings
    monkeypatch.setattr(settings, "google_api_key", settings.google_api_key or "mock-google-key")
    monkeypatch.setattr(settings, "mistral_api_key", settings.mistral_api_key or "mock-mistral-key")
    monkeypatch.setattr(settings, "tavily_api_key", settings.tavily_api_key or "mock-tavily-key")
    monkeypatch.setattr(settings, "cache_enabled", False)

    # 1. Block external network sockets and local service ports (allowing only internal asyncio loop pipes)
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        if host in ("127.0.0.1", "localhost", "::1"):
            if port in (6379, 80, 443, 8000):
                raise RuntimeError(f"Hermetic test blocked connection to local service {host}:{port}")
            return original_connect(self, address)
        raise RuntimeError(f"Hermetic test blocked external network connection to: {address}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # 2. Stub LLM structured generation and track calls
    monkeypatch.setattr(
        "app.ai.client.GenAIClient.generate_structured_content",
        llm_tracker.generate_structured_content
    )
    monkeypatch.setattr(
        "app.ai.client.GenAIClient.generate_content",
        AsyncMock(return_value="{}")
    )

    # 3. Mock LinkProcessor to avoid HTTP URL checks
    monkeypatch.setattr(
        "app.utils.link_processor.LinkProcessor.process_response",
        AsyncMock(side_effect=lambda resp: resp)
    )

    # 4. Mock Redis ping
    monkeypatch.setattr(
        "app.utils.redis_client.RedisClient.ping",
        AsyncMock(return_value=False)
    )

    # 5. Narrow patch for orchestrator sleep only
    with patch("app.ai.orchestrator.asyncio.sleep", new_callable=AsyncMock):
        yield

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
