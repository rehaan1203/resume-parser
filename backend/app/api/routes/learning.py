"""Learning management endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends
from app.ai.learning_orchestrator import LearningOrchestrator
from app.utils.logger import logger

router = APIRouter()

def get_learning_orchestrator() -> LearningOrchestrator:
    return LearningOrchestrator()

@router.get(
    "/stats",
    summary="Get learning statistics"
)
async def get_learning_stats(
    orchestrator: LearningOrchestrator = Depends(get_learning_orchestrator)
):
    """Get statistics about the learning system."""
    return await orchestrator.get_stats()

@router.get(
    "/patterns",
    summary="Get patterns for a context"
)
async def get_patterns_for_context(
    resume_domain: str,
    jd_domain: str,
    orchestrator: LearningOrchestrator = Depends(get_learning_orchestrator)
):
    """Get patterns relevant to a specific context."""
    context = {
        "resume_domain": resume_domain,
        "jd_domain": jd_domain
    }
    return await orchestrator.get_patterns_for_context(context)
