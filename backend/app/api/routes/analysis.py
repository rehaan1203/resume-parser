"""Analysis API routes with caching."""
from fastapi import APIRouter, HTTPException, status, Depends
from app.models.api_models import AnalysisRequest
from app.models.api_models import AnalysisResponse
from app.utils.cache_manager import CacheManager
from app.config import settings
from app.utils.logger import logger
import traceback
import json
import asyncio
from fastapi.responses import StreamingResponse
from typing import Optional

router = APIRouter()

@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze resume against job description",
    description="Returns analysis using AI with Redis caching"
)
async def analyze_resume(
    request: AnalysisRequest
):
    """
    Analyze a resume against a job description using Critic Loop.
    """
    try:
        logger.info(f"Analysis request received for resume length: {len(request.resume)}")
        
        request_data = request.dict()
        
        if settings.use_ai_service:
            logger.info("Using DeterministicOrchestrator for analysis")
            from app.ai.orchestrator import DeterministicOrchestrator
            orchestrator = DeterministicOrchestrator()
            result = await orchestrator.process(request_data)
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is not configured or available."
            )
            
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed due to an internal server error. Please try again."
        )

@router.post(
    "/analyze/stream",
    status_code=status.HTTP_200_OK,
    summary="Analyze resume against job description via Server-Sent Events",
    description="Streams real-time progress using SSE"
)
async def analyze_resume_stream(
    request: AnalysisRequest
):
    """
    Analyze a resume against a job description with real-time SSE progress.
    """
    if not settings.use_ai_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured or available."
        )

    async def event_generator():
        queue = asyncio.Queue()
        
        async def progress_callback(progress: int, message: str):
            await queue.put({"type": "progress", "progress": progress, "message": message})
            
        async def run_analysis():
            try:
                from app.ai.orchestrator import DeterministicOrchestrator
                orchestrator = DeterministicOrchestrator()
                result = await orchestrator.process(request.dict(), progress_callback)
                # Serialize using the response model to ensure camelCase keys (by_alias)
                from app.models.api_models import AnalysisResponse
                from fastapi.encoders import jsonable_encoder
                response_model = AnalysisResponse(**result)
                await queue.put({"type": "complete", "result": jsonable_encoder(response_model, by_alias=True)})
            except Exception as e:
                logger.error(f"Error in stream analysis: {str(e)}")
                await queue.put({"type": "error", "message": str(e)})
        
        # Start analysis in the background
        task = asyncio.create_task(run_analysis())
        
        while True:
            data = await queue.get()
            # Format as Server-Sent Event
            yield f"data: {json.dumps(data)}\n\n"
            
            if data["type"] in ["complete", "error"]:
                break
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")
@router.delete(
    "/cache/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset analysis cache",
    description="Clears the redis cache for a fresh analysis"
)
async def reset_cache():
    """
    Clear all cached analysis results.
    """
    manager = CacheManager()
    success = await manager.clear_all()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset cache"
        )
        
    return {"status": "success", "message": "Cache cleared successfully"}
