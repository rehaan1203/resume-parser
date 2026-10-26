"""Pytest fixtures and hermetic environment configuration."""
import os
import socket
from unittest.mock import AsyncMock, patch
import pytest

# Register custom markers
def pytest_configure(config):
    config.addinivalue_line("markers", "live: tests that require real external network, APIs, or services")

# Default settings overrides for testing
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("CORS_ORIGINS", '["*"]')

class GlobalLLMCallTracker:
    def __init__(self):
        self.call_count = 0
        self.calls = []

    async def generate_structured_content(self, prompt: str, output_schema: dict, **kwargs):
        self.call_count += 1
        self.calls.append({"prompt": prompt, "schema": output_schema})
        if "summary" in output_schema:
            return {"summary": "Candidate shows strong alignment with the technical requirements."}
        if "status" in output_schema and "scope" in output_schema:
            return {
                "status": "found",
                "years": 4,
                "evidence_quote": "4 years of experience",
                "scope": "total_career"
            }
        if "status" in output_schema and "years" in output_schema:
            return {
                "status": "found",
                "years": 4,
                "evidence_quote": "4 years experience"
            }
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
            return {"years": 4}
        if "status" in output_schema:
            return {"status": "not_found", "years": None, "evidence_quote": None}
        return {}

@pytest.fixture
def llm_tracker():
    return GlobalLLMCallTracker()

@pytest.fixture(autouse=True)
def hermetic_environment(request, monkeypatch, llm_tracker):
    """Hermetic test fixture blocking external sockets, stubbing AI calls, and isolating services unless marked 'live'."""
    from app.config import settings
    settings.orchestrator_progress_delay = 0.0

    if request.node.get_closest_marker("live"):
        yield
        return

    # Provide hermetic mock keys so GenAIClient initializes in memory without ValueError
    monkeypatch.setattr(settings, "google_api_key", settings.google_api_key or "mock-google-key")
    monkeypatch.setattr(settings, "mistral_api_key", settings.mistral_api_key or "mock-mistral-key")
    monkeypatch.setattr(settings, "tavily_api_key", settings.tavily_api_key or "mock-tavily-key")
    monkeypatch.setattr(settings, "cache_enabled", False)

    # 1. Block external network sockets and local service ports (both sync and async Windows IOCP)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def check_address(host, port=None):
        host_str = host.decode("utf-8", errors="ignore") if isinstance(host, bytes) else str(host)
        if host_str not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError(f"Hermetic test blocked external network call to: {host_str}:{port}")
        if port in (6379, 80, 443, 8000):
            raise RuntimeError(f"Hermetic test blocked connection to local service {host_str}:{port}")

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        check_address(host, port)
        return original_connect(self, address)

    def guarded_connect_ex(self, address):
        host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        check_address(host, port)
        return original_connect_ex(self, address)

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        check_address(host, port)
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    # 2. Stub LLM structured generation and track calls
    monkeypatch.setattr(
        "app.ai.client.GenAIClient.generate_structured_content",
        llm_tracker.generate_structured_content
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

    # 5. Patch orchestrator sleep
    with patch("app.ai.orchestrator.asyncio.sleep", new_callable=AsyncMock):
        yield

