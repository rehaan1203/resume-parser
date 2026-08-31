from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.ai.client import GenAIClient
from app.utils.logger import logger

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
    
    prompt = f"""
You are a career coach creating a transition roadmap for someone moving from {resume_domain} to {jd_domain}.

## Resume: {resume[:2000]}
## Job Description: {jd[:2000]}

### CRITICAL RULES:
1. This is a COMPLETE CAREER TRANSITION (12-18 months)
2. Return ONLY transition content
3. NO skill gaps (they have no skills in the target domain)
4. NO ATS optimization tips
5. NO seniority comparison

### Return ONLY this JSON:
{{
    "type": "career_change",
    "title": "Career Change: {resume_domain} → {jd_domain}",
    "estimated_timeline": "12-18 months",
    "phases": [
        {{
            "phase": 1,
            "duration": "3-4 months",
            "focus": "Foundational Skills",
            "activities": [
                "Learn core {jd_domain} concepts",
                "Build foundational {jd_domain} skills"
            ]
        }},
        {{
            "phase": 2,
            "duration": "4-6 months",
            "focus": "Core Domain Skills",
            "activities": [
                "Master {jd_domain} fundamentals",
                "Practice with real-world projects"
            ]
        }},
        {{
            "phase": 3,
            "duration": "3-4 months",
            "focus": "Advanced Topics & Specialization",
            "activities": [
                "Learn advanced {jd_domain} techniques",
                "Specialize in specific areas"
            ]
        }},
        {{
            "phase": 4,
            "duration": "2-4 months",
            "focus": "Portfolio & Job Search",
            "activities": [
                "Build comprehensive portfolio",
                "Apply to junior roles",
                "Network in the industry"
            ]
        }}
    ]
}}
"""
    
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
    
    prompt = f"""
You are a career coach providing transition resources for someone moving from {resume_domain} to {jd_domain}.

## Resume: {resume[:2000]}
## Job Description: {jd[:2000]}

### CRITICAL RULES:
1. Return ONLY transition resources
2. Include ACTUAL working links for each resource
3. Use real, verified URLs
4. Prefer free resources where possible

### Resource Types:
- Education: Free/paid courses with links
- Certifications: Certification programs with links
- Portfolio: Platforms and tools with links
- Resume Strategy: General advice (no links needed)

### Return ONLY this JSON:
{{
    "education": [
        {{"name": "Course Name", "platform": "Platform", "url": "https://..."}},
        {{"name": "Course Name", "platform": "Platform", "url": "https://..."}}
    ],
    "certifications": [
        {{"name": "Certification Name", "provider": "Provider", "url": "https://..."}},
        {{"name": "Certification Name", "provider": "Provider", "url": "https://..."}}
    ],
    "portfolio": [
        {{"name": "Resource Name", "description": "What it is", "url": "https://..."}}
    ],
    "resume_strategy": [
        "Advice 1",
        "Advice 2"
    ]
}}
"""
    
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
