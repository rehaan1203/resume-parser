"""Prompts and builder functions for ATS optimization and career transition advice."""
from typing import List

STANDARD_ATS_PROMPT_VERSION = "v1"
TRANSITION_ATS_PROMPT_VERSION = "v1"
TRANSITION_TIPS_PROMPT_VERSION = "v1"
ATS_OPTIMIZATION_PROMPT_VERSION = "v1"


def build_standard_ats_prompt(gaps: List[str]) -> str:
    """Build prompt for standard skill-gap based ATS optimization tips."""
    return f"""
        Provide specific, actionable ATS optimization tips based on the candidate's skill gaps.
        Skill gaps: {', '.join(gaps)}
        
        Output format exactly:
        1. 'keywords': A list of specific keywords they should add (e.g., "Add 'Technology Law' to Core Competencies").
        2. 'phrasing': A list of objects with 'original' and 'suggested' bullet points demonstrating how to rewrite experience to highlight the missing skills.
        3. 'formatting_tips': 2-3 standard ATS formatting tips.
        
        Do not invent requirements not related to the gaps.
        """


def build_transition_ats_prompt(
    resume_domain: str,
    jd_domain: str,
    gaps: List[str]
) -> str:
    """Build prompt for cross-domain career transition ATS optimization tips."""
    return f"""
            Provide specific, actionable Career Transition ATS optimization tips for a candidate moving from {resume_domain} to {jd_domain}.
            Missing technical skills: {', '.join(gaps)}
            
            Output format exactly:
            1. 'keywords': A list of foundational keywords they should learn and add (e.g., "Add 'Python' to Core Competencies").
            2. 'phrasing': A list of objects with 'original' and 'suggested' bullet points demonstrating how to translate {resume_domain} experience into transferable skills for {jd_domain}.
            3. 'formatting_tips': 2-3 standard ATS formatting tips (e.g. use functional resume format).
            """


def build_transition_tips_prompt(
    resume_domain: str,
    jd_domain: str,
    resume: str,
    jd: str
) -> str:
    """Build prompt for transition resources (education, certifications, portfolio)."""
    return f"""
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


ATS_OPTIMIZATION_PROMPT = """
Optimize this resume for ATS systems based on the job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

FRICTION POINTS:
{friction_points}

Provide specific keyword additions, phrasing improvements, and formatting tips.
Return JSON with suggestions object containing keywords_to_add, phrasing_improvements, section_reordering, formatting_tips, and ats_score.
"""
