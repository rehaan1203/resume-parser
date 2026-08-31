"""Health check API routes."""
from fastapi import APIRouter, status
from app.config import settings
from app.utils.datetime_utils import get_utc_timestamp

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
