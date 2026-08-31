"""Advanced AI feature routes."""
from fastapi import APIRouter, HTTPException, status, Depends
from app.models.api_models import AnalysisRequest
from app.ai.orchestrator import DeterministicOrchestrator
from app.ai.interview_questions import InterviewQuestionGenerator
from app.ai.ats_optimizer import ATSOptimizer
from app.ai.career_advisor import CareerAdvisor
from app.ai.client import GenAIClient
from app.config import settings
from app.utils.logger import logger

router = APIRouter()

def get_ai_client():
    if not settings.use_ai_service or not settings.google_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not available"
        )
    return GenAIClient()


@router.post(
    "/advanced/interview-questions",
    summary="Generate interview questions"
)
async def generate_interview_questions(
    request: AnalysisRequest,
    client: GenAIClient = Depends(get_ai_client)
):
    """Generate interview questions based on resume and JD."""
    try:
        # Get analysis first
        orchestrator = DeterministicOrchestrator()
        analysis = await orchestrator.process(request.dict())
        skill_gaps = analysis.get("skill_gaps", [])
        strengths = analysis.get("strengths", [])
        
        # Generate questions
        generator = InterviewQuestionGenerator(client)
        questions = await generator.generate_questions(
            resume=request.resume,
            jd=request.jd_text or "",
            skill_gaps=skill_gaps,
            strengths=strengths
        )
        
        return {
            "questions": questions,
            "total": len(questions),
            "metadata": {
                "generated_by": settings.gemini_model,
                "skill_gaps_used": skill_gaps
            }
        }
        
    except Exception as e:
        logger.error(f"Interview questions generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post(
    "/advanced/ats-optimize",
    summary="Get ATS optimization suggestions"
)
async def optimize_for_ats(
    request: AnalysisRequest,
    client: GenAIClient = Depends(get_ai_client)
):
    """Get ATS optimization suggestions."""
    try:
        # Get analysis first
        orchestrator = DeterministicOrchestrator()
        analysis = await orchestrator.process(request.dict())
        friction_points = analysis.get("friction_points", [])
        
        # Generate optimization
        optimizer = ATSOptimizer(client)
        suggestions = await optimizer.optimize(
            resume=request.resume,
            jd=request.jd_text or "",
            friction_points=friction_points
        )
        
        return {
            "suggestions": suggestions,
            "metadata": {
                "generated_by": settings.gemini_model,
                "friction_points_analyzed": len(friction_points)
            }
        }
        
    except Exception as e:
        logger.error(f"ATS optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post(
    "/advanced/career-advice",
    summary="Get career guidance"
)
async def get_career_advice(
    request: AnalysisRequest,
    client: GenAIClient = Depends(get_ai_client)
):
    """Get long-term career guidance."""
    try:
        # Get analysis first
        orchestrator = DeterministicOrchestrator()
        analysis = await orchestrator.process(request.dict())
        skill_gaps = analysis.get("skill_gaps", [])
        
        # Get career advice
        advisor = CareerAdvisor(client)
        advice = await advisor.get_advice(
            resume=request.resume,
            experience=request.experience or "",
            goals=request.career_goals or "",
            skill_gaps=skill_gaps
        )
        
        return {
            "advice": advice,
            "metadata": {
                "generated_by": settings.gemini_model,
                "skill_gaps_used": skill_gaps
            }
        }
        
    except Exception as e:
        logger.error(f"Career advice generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
