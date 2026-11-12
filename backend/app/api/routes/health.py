"""Health check API routes."""
from fastapi import APIRouter, Depends, status
from app.config import settings
from app.utils.datetime_utils import get_utc_timestamp
from app.utils.security import require_admin_access

router = APIRouter()

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint"
)
async def health_check():
    """
    Check if the API is running and healthy.
    """
    return {
        "status": "ok",
        "version": settings.app_version,
        "timestamp": get_utc_timestamp()
    }

@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe"
)
async def readiness_check():
    """
    Check if the API is ready to handle requests.
    """
    return {
        "status": "ready",
        "mock_mode": settings.use_mock,
        "timestamp": get_utc_timestamp()
    }

@router.post(
    "/health/audit-catalog",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_access)],
    summary="Trigger RAG Catalog Health Audit"
)
async def trigger_catalog_health_audit():
    """
    Audit all URLs in RAG knowledge catalogs concurrently and report health status.
    """
    from app.tasks.catalog_health import CatalogHealthAuditor
    auditor = CatalogHealthAuditor()
    report = await auditor.audit_all_catalogs(auto_suggest_replacements=True)
    return report

@router.get(
    "/health/catalog-status",
    status_code=status.HTTP_200_OK,
    summary="Get Latest RAG Catalog Health Status"
)
async def get_catalog_health_status():
    """
    Retrieve the most recent RAG catalog health audit report.
    """
    from app.tasks.catalog_health import get_latest_audit_report
    return await get_latest_audit_report()
