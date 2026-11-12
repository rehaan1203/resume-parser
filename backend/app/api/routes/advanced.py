"""Advanced AI feature routes."""
from typing import Dict, Any, List, Optional
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
    if not settings.use_ai_service or not any([settings.google_api_key, settings.mistral_api_key, settings.groq_api_key]):
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
            "degraded_sections": ["interview_questions"] if generator.is_fallback else [],
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
            "degraded_sections": ["ats_optimization"] if optimizer.is_fallback else [],
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
            "degraded_sections": ["career_advice"] if advisor.is_fallback else [],
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


@router.get(
    "/advanced/catalog-health",
    summary="Get RAG Knowledge Base Catalog Health Report"
)
async def get_catalog_health():
    """Retrieve the latest health check audit report for RAG catalogs."""
    import os
    import json
    reports_path = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge", "reports", "health_report.json")
    if not os.path.exists(reports_path):
        return {
            "status": "pending",
            "message": "Health audit has not been run yet. Run scripts/verify_catalog_health.py to generate."
        }
    try:
        with open(reports_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to read catalog health report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read health report."
        )


@router.post(
    "/advanced/roadmap/customize",
    summary="Filter and customize roadmap resources using candidate criteria"
)
async def customize_roadmap_resources(payload: Dict[str, Any]):
    """Dynamically re-rank and filter verified learning resources based on pacing and format."""
    skills = payload.get("missing_skills", [])
    domain = payload.get("domain", "tech")
    max_hours = payload.get("max_hours_per_week", 10)
    preferred_format = payload.get("preferred_format", "all")  # all, video, documentation, course
    free_only = payload.get("free_only", False)

    from app.knowledge.retriever import get_retriever
    retriever = get_retriever()

    try:
        raw_resources = await retriever.search_for_gaps(skills=skills, domain=domain, limit=12)
        filtered = []

        for r in raw_resources:
            # Free only filter
            if free_only and not r.is_free:
                continue
            # Format filter
            if preferred_format != "all":
                if preferred_format == "video" and r.type.value != "youtube_video":
                    continue
                elif preferred_format == "documentation" and r.type.value != "documentation":
                    continue
                elif preferred_format == "course" and r.type.value not in ("course", "certification"):
                    continue
            # Pacing filter (skip resources whose duration exceeds weekly budget by 2x)
            if r.duration_hours and r.duration_hours > (max_hours * 2):
                continue
            filtered.append(r.model_dump())

        return {
            "domain": domain,
            "total_matches": len(filtered),
            "customized_resources": filtered,
            "criteria_applied": {
                "max_hours_per_week": max_hours,
                "preferred_format": preferred_format,
                "free_only": free_only
            }
        }
    except Exception as e:
        logger.error(f"Error customizing roadmap: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/rag/diagnostics/catalog-health",
    summary="Get RAG Knowledge Base Catalog Health Report (Alias)"
)
async def get_rag_catalog_health():
    """RAG-namespaced alias for catalog health report."""
    return await get_catalog_health()


@router.post(
    "/rag/customize-roadmap",
    summary="Filter and customize roadmap resources (Alias)"
)
async def customize_rag_roadmap(payload: Dict[str, Any]):
    """RAG-namespaced alias for roadmap customization."""
    return await customize_roadmap_resources(payload)
