"""Prompts and builder functions for candidate analysis and explanation."""
from typing import List

EXECUTIVE_SUMMARY_PROMPT_VERSION = "v1"
DOMAIN_MISMATCH_PROMPT_VERSION = "v1"
FRICTION_ANALYSIS_PROMPT_VERSION = "v1"
SAMPLE_ANALYSIS_PROMPT_VERSION = "v1"


def build_executive_summary_prompt(
    score: int,
    strengths: List[str],
    gaps: List[str],
    seniority_gap: int
) -> str:
    """Build prompt for generating a concise executive summary."""
    return f"""
        Write a concise, professional 3-4 sentence executive summary for a candidate.
        They scored {score}% on the job match.
        Their key strengths are: {', '.join(strengths[:3])}.
        Their key skill gaps are: {', '.join(gaps[:3])}.
        They have a seniority gap of {seniority_gap} years (0 means no gap).
        
        Keep it objective, highlighting strengths and mentioning areas for growth. Do not invent new skills or facts.
        """


def build_mismatch_prompt(resume_domain: str, jd_domain: str) -> str:
    """Build prompt for explaining why domains are mismatched."""
    return f"""
        Provide a concise, 2-sentence explanation of why a candidate with a {resume_domain} background is fundamentally mismatched for a {jd_domain} role. 
        Focus on the completely different core competencies and daily responsibilities required.
        """


FRICTION_ANALYSIS_PROMPT = """Analyze the semantic friction between this resume and job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

FRICTION POINTS IDENTIFIED (from embedding analysis):
{friction_points}

Provide a detailed analysis with:
1. Missing skills and qualifications (list 3-5 specific skills)
2. Phrasing mismatches (where the resume says X but JD expects Y, list 2-3)
3. Experience level gaps (if any)
4. Actionable suggestions for improvement (list 3-5 specific actions)

Format as JSON with this exact structure:
{{
  "skill_gaps": ["string"],
  "phrasing_mismatches": [{{"resume_phrase": "string", "jd_phrase": "string", "suggestion": "string"}}],
  "experience_analysis": {{"gap": "string", "suggestion": "string"}},
  "improvement_suggestions": ["string"]
}}"""


SAMPLE_ANALYSIS_PROMPT = """Analyze the friction between this resume and job description. Be specific and critical.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Return a JSON object with:
{{
  "overall_score": 0,
  "friction_points": [
    {{"category": "skills|experience|education|phrasing", 
     "severity": "critical|warning|info",
     "description": "string",
     "suggestion": "string"}}
  ],
  "skill_gaps": ["string"],
  "strengths": ["string"]
}}"""
