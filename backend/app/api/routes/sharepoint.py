"""
FastAPI route for Microsoft SharePoint Job Description Integration.

Provides endpoints for monitoring SharePoint connection status, inspecting active
job requisitions, and refreshing the in-memory JD cache.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from app.services.sharepoint_service import sharepoint_service
from app.utils.logger import logger
from app.utils.security import require_admin_access

router = APIRouter(prefix="/sharepoint", tags=["SharePoint JDs"])


@router.get(
    "/status",
    summary="Check SharePoint Connection & Folder Visibility",
    description="Validates SharePoint site resolution, Document Library Drive access, and active JD counts.",
)
async def get_sharepoint_status() -> Dict[str, Any]:
    """Test SharePoint site and folder connection."""
    try:
        result = await sharepoint_service.test_connection()
        return result
    except Exception as e:
        logger.error(f"Error checking SharePoint status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SharePoint connection check failed.",
        )


@router.get(
    "/jobs",
    summary="List Active Job Descriptions in SharePoint",
    description="Returns metadata and titles of all active JDs currently loaded in-memory from SharePoint.",
)
async def list_active_jobs() -> Dict[str, Any]:
    """Retrieve all active SharePoint JDs."""
    try:
        jds = await sharepoint_service.fetch_active_job_descriptions()
        return {
            "success": True,
            "count": len(jds),
            "jobs": [
                {
                    "id": jd.get("id"),
                    "title": jd.get("title"),
                    "filename": jd.get("filename"),
                    "lastModified": jd.get("lastModified"),
                    "size": jd.get("size"),
                }
                for jd in jds
            ],
        }
    except Exception as e:
        logger.error(f"Error listing SharePoint jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list SharePoint jobs.",
        )


@router.post(
    "/refresh",
    dependencies=[Depends(require_admin_access)],
    summary="Force Refresh SharePoint JD In-Memory Cache",
    description="Invalidates the current in-memory cache and immediately re-queries SharePoint for updated files.",
)
async def refresh_sharepoint_cache() -> Dict[str, Any]:
    """Force re-sync active JDs from SharePoint."""
    try:
        jds = await sharepoint_service.fetch_active_job_descriptions(force_refresh=True)
        return {
            "success": True,
            "message": "SharePoint JD cache refreshed successfully.",
            "activeJdCount": len(jds),
            "jobs": [j["title"] for j in jds],
        }
    except Exception as e:
        logger.error(f"Error refreshing SharePoint cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh SharePoint cache.",
        )

