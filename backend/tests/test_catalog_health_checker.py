"""Unit tests for Option 4 Catalog Health Checker and Diagnostic Endpoint."""
import os
import json
import asyncio
import pytest
from scripts.verify_catalog_health import check_url_health, audit_all_catalogs
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_diagnostic_endpoint_catalog_health():
    """Verify GET /api/v1/advanced/catalog-health returns valid report payload."""
    response = client.get("/api/v1/advanced/catalog-health")
    assert response.status_code == 200
    data = response.json()
    if data.get("status") == "pending":
        assert "message" in data
    else:
        assert "total_resources" in data
        assert "health_percentage" in data
        assert data["total_resources"] >= 25
        assert data["broken"] == 0


def test_check_url_health_logic(monkeypatch):
    """Verify check_url_health parses response codes properly with mock client."""
    async def _run():
        import httpx
        from unittest.mock import AsyncMock, MagicMock
        
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.head.return_value = mock_resp

        semaphore = asyncio.Semaphore(2)
        res = await check_url_health(mock_client, semaphore, "https://fastapi.tiangolo.com/tutorial/")
        assert res["url"] == "https://fastapi.tiangolo.com/tutorial/"
        assert res["health_status"] == "active"
        assert res["status_code"] == 200

        # Simulate 404
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_client.head.return_value = mock_resp_404
        res_404 = await check_url_health(mock_client, semaphore, "https://invalid.org/broken")
        assert res_404["health_status"] == "broken"
        assert res_404["status_code"] == 404

    asyncio.run(_run())
