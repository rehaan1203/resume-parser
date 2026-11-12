"""
FastAPI route for Autonomous Microsoft Outlook HR Agent.

Provides endpoints for polling candidate emails, health check verification,
and on-demand processing of incoming resumes.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.services.outlook_service import outlook_service
from app.utils.logger import logger
from app.utils.security import require_admin_access

router = APIRouter(prefix="/outlook", tags=["Outlook HR Agent"])


@router.get(
    "/status",
    summary="Check Outlook Connector & Mailbox Health",
    description="Validates Azure AD credentials and tests Microsoft Graph connection to the target mailbox.",
)
async def get_outlook_status() -> Dict[str, Any]:
    """Test Microsoft Graph token acquisition and mailbox status."""
    try:
        result = await outlook_service.test_connection()
        if isinstance(result, dict):
            result["pollerPaused"] = outlook_service.is_poller_paused()
        return result
    except Exception as e:
        logger.error(f"Error checking Outlook status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Outlook status check failed.",
        )


@router.post(
    "/poller/pause",
    dependencies=[Depends(require_admin_access)],
    summary="Pause Background Outlook Poller",
    description="Temporarily pauses background inbox polling without restarting the server (useful when working in the frontend UI).",
)
async def pause_outlook_poller() -> Dict[str, Any]:
    """Pause autonomous background Outlook polling."""
    outlook_service.pause_poller()
    return {"success": True, "pollerPaused": True}


@router.post(
    "/poller/resume",
    dependencies=[Depends(require_admin_access)],
    summary="Resume Background Outlook Poller",
    description="Resumes background inbox polling after being paused.",
)
async def resume_outlook_poller() -> Dict[str, Any]:
    """Resume autonomous background Outlook polling."""
    outlook_service.resume_poller()
    return {"success": True, "pollerPaused": False}


@router.post(
    "/poll",
    dependencies=[Depends(require_admin_access)],
    summary="Poll Inbox & Process Candidate Resumes",
    description=(
        "Fetches unread emails from the configured Outlook mailbox, streams attachments in-memory, "
        "runs the Friction AI matching analysis, dispatches professional HTML verdict emails, and marks messages as read."
    ),
)
async def poll_inbox(
    limit: Optional[int] = Query(default=10, ge=1, le=50, description="Max emails to process in batch"),
) -> Dict[str, Any]:
    """Poll and process unread candidate resumes autonomously."""
    if not outlook_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outlook service is not configured. Please verify Azure credentials in environment settings.",
        )

    try:
        summary = await outlook_service.poll_and_process_inbox(limit=limit)
        return summary
    except Exception as e:
        logger.error(f"Error during Outlook inbox polling: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inbox polling failed due to an internal error.",
        )

