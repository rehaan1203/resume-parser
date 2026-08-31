"""Feedback collection endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends, Header
from app.models.domain_models import FeedbackRequest
from app.ai.learning_orchestrator import LearningOrchestrator
from app.utils.logger import logger
from typing import Optional

router = APIRouter()

def get_learning_orchestrator() -> LearningOrchestrator:
    return LearningOrchestrator()

@router.post(
    "/feedback",
    summary="Submit feedback for an analysis"
)
async def submit_feedback(
    request: FeedbackRequest,
    session_id: Optional[str] = Header(None),
    orchestrator: LearningOrchestrator = Depends(get_learning_orchestrator)
):
    """Submit explicit feedback for an analysis."""
    # Validate basic auth / session if needed
    if not session_id:
        # Just logging for now, we could raise 401
        logger.warning("Feedback submitted without session ID")
        
    try:
        # In a real system, we'd fetch the context here. For now passing empty.
        context = {
            "resume_domain": "unknown",
            "jd_domain": "unknown",
            "score": 0,
            "keywords": []
        }
        
        result = await orchestrator.process_feedback(
            analysis_id=request.analysis_id,
            rating=request.rating,
            comment=request.comment,
            corrections=request.corrections,
            context=context
        )
        return result
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
