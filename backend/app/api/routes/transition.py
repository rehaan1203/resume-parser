from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.ai.client import GenAIClient
from app.utils.logger import logger
from app.prompts.roadmap_prompt import build_transition_roadmap_prompt
from app.prompts.ats_prompt import build_transition_tips_prompt

router = APIRouter()

class TransitionRequest(BaseModel):
    resume: str = Field(..., min_length=100)
    jd: str = Field(..., min_length=100)
    resume_domain: str
    jd_domain: str

class TransitionResponse(BaseModel):
    status: str
    resume_domain: str
    jd_domain: str
    score: int
    roadmap: dict
    transition_tips: dict
    seniority: dict

@router.post("/transition-plan", response_model=TransitionResponse)
async def generate_transition_plan(request: TransitionRequest):
    """
    Generate ONLY transition content for domain mismatch.
    NO ATS Optimization Tips, NO Skill Gaps, NO Strengths, NO Phrasing.
    """
    try:
        logger.info(f"📋 Generating transition plan: {request.resume_domain} → {request.jd_domain}")
        
        # Generate transition roadmap
        roadmap = await generate_transition_roadmap(
            resume_domain=request.resume_domain,
            jd_domain=request.jd_domain,
            resume=request.resume,
            jd=request.jd
        )
        
        # Generate transition tips (education, certifications, portfolio)
        transition_tips = await generate_transition_tips(
            resume_domain=request.resume_domain,
            jd_domain=request.jd_domain,
            resume=request.resume,
            jd=request.jd
        )
        
        return TransitionResponse(
            status="transition_plan",
            resume_domain=request.resume_domain,
            jd_domain=request.jd_domain,
            score=0,
            roadmap=roadmap,
            transition_tips=transition_tips,
            seniority={
                "status": "domain_mismatch",
                "message": "Seniority comparison is not applicable for a career transition."
            }
        )
        
    except Exception as e:
        logger.error(f"Transition plan generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate transition plan: {str(e)}"
        )


async def generate_transition_roadmap(resume_domain: str, jd_domain: str, resume: str, jd: str) -> dict:
    """
    Generate a 12-18 month career transition roadmap using LLM.
    This is the ONLY content generated for the roadmap.
    """
    client = GenAIClient()
    
    prompt = build_transition_roadmap_prompt(
        resume_domain=resume_domain,
        jd_domain=jd_domain,
        resume=resume,
        jd=jd
    )
    
    response = await client.generate_structured_content(
        prompt=prompt,
        output_schema={
            "type": "string",
            "title": "string",
            "estimated_timeline": "string",
            "phases": [
                {
                    "phase": 0,
                    "duration": "string",
                    "focus": "string",
                    "activities": ["string"]
                }
            ]
        },
        temperature=0.3
    )
    
    return response


async def generate_transition_tips(resume_domain: str, jd_domain: str, resume: str, jd: str) -> dict:
    """
    Generate transition tips (education, certifications, portfolio) using LLM.
    NO ATS optimization tips (keywords, phrasing, formatting).
    """
    client = GenAIClient()
    
    prompt = build_transition_tips_prompt(
        resume_domain=resume_domain,
        jd_domain=jd_domain,
        resume=resume,
        jd=jd
    )
    
    response = await client.generate_structured_content(
        prompt=prompt,
        output_schema={
            "education": [{"name": "string", "platform": "string", "url": "string"}],
            "certifications": [{"name": "string", "provider": "string", "url": "string"}],
            "portfolio": [{"name": "string", "description": "string", "url": "string"}],
            "resume_strategy": ["string"]
        },
        temperature=0.3
    )
    
    return response
