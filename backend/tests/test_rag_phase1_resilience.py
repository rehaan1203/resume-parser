"""Comprehensive End-to-End Tests for RAG Phase 1: Zero-Quota Fallback & Catalog Health Auditor."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.utils.link_replacer import LinkReplacer
from app.utils.link_processor import LinkProcessor
from app.tasks.catalog_health import CatalogHealthAuditor, get_latest_audit_report
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def replacer():
    return LinkReplacer()

@pytest.fixture
def processor():
    return LinkProcessor()

# -------------------------------------------------------------
# 1. Zero-Quota Canonical Synthesizer Tests
# -------------------------------------------------------------
def test_synthesizer_video_topic(replacer):
    """Ensure video keywords synthesize canonical YouTube education search URLs."""
    url = replacer.synthesize_canonical_search_url("Kubernetes Deployment", link_type="video")
    assert "youtube.com/results?search_query=" in url
    assert "Kubernetes" in url or "kubernetes" in url.lower()
    assert "tutorial" in url

def test_synthesizer_certification_topic(replacer):
    """Ensure certification keywords synthesize canonical Coursera or Cloud vendor certification URLs."""
    azure_cert = replacer.synthesize_canonical_search_url("Azure Fundamentals AZ-900", link_type="certification")
    assert "learn.microsoft.com" in azure_cert

    aws_cert = replacer.synthesize_canonical_search_url("AWS Solutions Architect", link_type="certification")
    assert "aws.amazon.com/certification" in aws_cert

    gen_cert = replacer.synthesize_canonical_search_url("PMP Project Management", link_type="certification")
    assert "coursera.org/search?query=" in gen_cert

def test_synthesizer_domain_centers(replacer):
    """Ensure domain-specific technologies synthesize authoritative platform URLs."""
    docker_url = replacer.synthesize_canonical_search_url("Docker Container Networking", link_type="course")
    assert "docs.docker.com" in docker_url

    legal_url = replacer.synthesize_canonical_search_url("GDPR Compliance Essentials", link_type="article")
    assert "coursera.org/search?query=" in legal_url
    assert "compliance" in legal_url

    health_url = replacer.synthesize_canonical_search_url("Clinical Data Standards FHIR", link_type="course")
    assert "coursera.org/search?query=" in health_url
    assert "healthcare" in health_url

# -------------------------------------------------------------
# 2. Major Platform Preservation Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_major_platform_preservation(replacer):
    """Verify that a valid major platform link (e.g. YouTube, Coursera) is preserved and NOT replaced with None."""
    valid_yt = "https://www.youtube.com/watch?v=Jfvg3CSKTQ0"
    preserved = await replacer.find_replacement(valid_yt, "Azure Overview", "video")
    assert preserved == valid_yt, f"Expected {valid_yt} to be preserved, got {preserved}"

# -------------------------------------------------------------
# 3. Complete API Failure / Zero-Quota Fallback Resilience
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_find_replacement_zero_quota_on_api_outage(replacer):
    """Simulate total third-party API outage (Tavily & YouTube throwing exceptions)."""
    with patch.object(replacer, "find_course_replacement", side_effect=Exception("429 Quota Exceeded")):
        with patch.object(replacer, "find_video_replacement", side_effect=Exception("Daily YouTube Quota Exceeded")):
            replacement = await replacer.find_replacement("https://dead-docs-site.com/broken-page", "React Hooks State Management", "course")
            assert replacement is not None
            assert replacement.startswith("http")
            assert "coursera.org" in replacement or "youtube.com" in replacement

# -------------------------------------------------------------
# 4. LinkProcessor Zero-Quota Fallback Integration
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_link_processor_guaranteed_link_healing():
    """Verify that LinkProcessor replaces dead URLs with canonical links and NEVER leaves None."""
    import importlib
    import app.utils.link_processor as lp_mod
    importlib.reload(lp_mod)
    processor = lp_mod.LinkProcessor()

    fake_response = {
        "title": "Cloud Engineer Path",
        "steps": [
            {
                "day": 1,
                "action": "Learn Cloud Fundamentals",
                "resources": ["https://learn.microsoft.com/broken-dead-link-404-never-existed"]
            }
        ]
    }

    # Mock validator returning 404
    with patch.object(processor.validator, "validate_many", return_value={
        "https://learn.microsoft.com/broken-dead-link-404-never-existed": {"status_code": 404, "status": "error"}
    }):
        # Mock replacer search returning empty
        with patch.object(processor.replacer, "find_course_replacement", return_value=None):
            with patch.object(processor.replacer, "find_video_replacement", return_value=None):
                with patch.object(processor.replacer, "find_article_replacement", return_value=None):
                    processed = await processor.process_response(fake_response)
                    res_list = processed["steps"][0]["resources"]
                    assert len(res_list) == 1
                    healed_url = res_list[0]
                    assert healed_url is not None
                    assert "https://learn.microsoft.com/broken-dead-link-404-never-existed" not in healed_url
                    assert healed_url.startswith("http")

# -------------------------------------------------------------
# 5. Catalog Health Auditor Endpoints & Integration
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_catalog_health_auditor_execution():
    """Verify that the auditor scans catalogs and returns a structured report."""
    auditor = CatalogHealthAuditor()

    # Mock validator returning mostly 200 and one 404 for speed and reliability
    async def mock_validate_many(urls):
        results = {u: {"status_code": 200, "status": "ok"} for u in urls}
        if urls:
            results[urls[0]] = {"status_code": 404, "status": "error"}
        return results

    with patch.object(auditor.validator, "validate_many", side_effect=mock_validate_many):
        report = await auditor.audit_all_catalogs(auto_suggest_replacements=True)

        assert "total_resources" in report
        assert "healthy_count" in report
        assert "broken_count" in report
        assert "health_percentage" in report
        assert report["total_resources"] > 0
        assert report["healthy_count"] + report["broken_count"] == report["total_resources"]
        assert report["broken_count"] >= 1
        assert len(report["broken_details"]) >= 1
        assert "suggested_replacement" in report["broken_details"][0]

@pytest.mark.asyncio
async def test_catalog_health_api_endpoints():
    """Verify HTTP endpoints for catalog health audit."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Mock audit to return valid fixture
        with patch("app.tasks.catalog_health.CatalogHealthAuditor.audit_all_catalogs") as mock_audit:
            mock_audit.return_value = {
                "status": "healthy",
                "timestamp": "2026-11-03T10:00:00Z",
                "total_resources": 28,
                "healthy_count": 28,
                "broken_count": 0,
                "health_percentage": "100.0%",
                "broken_details": []
            }
            # 1. Trigger audit
            resp = await ac.post("/api/v1/health/audit-catalog")
            assert resp.status_code == 200
            data = resp.json()
            assert "total_resources" in data
            assert data["total_resources"] == 28

        # 2. Check cached status
        with patch("app.tasks.catalog_health.get_latest_audit_report") as mock_status:
            mock_status.return_value = {
                "status": "healthy",
                "timestamp": "2026-11-03T10:00:00Z",
                "total_resources": 28
            }
            status_resp = await ac.get("/api/v1/health/catalog-status")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert status_data["total_resources"] == 28

