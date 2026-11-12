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


def build_rag_ats_prompt(
    gaps: List[str],
    phrasing_templates: List[dict] = None
) -> str:
    """Build prompt for ATS optimization grounded in verified STAR phrasing templates."""
    templates_str = ""
    if phrasing_templates:
        lines = []
        for t in phrasing_templates[:3]:
            verbs = ", ".join(t.get("action_verbs", [])[:3])
            lines.append(
                f"- Domain: {t.get('domain', '').title()} | Verbs: {verbs}\n"
                f"  Formula: {t.get('star_template', '')}\n"
                f"  Example Rewrite: \"{t.get('example_after', '')}\""
            )
        templates_str = "\n".join(lines)
    else:
        templates_str = "None provided. Use standard STAR framework (Situation, Task, Action, Result)."

    return f"""
        Provide specific, actionable ATS optimization tips based on the candidate's skill gaps.
        Skill gaps: {', '.join(gaps)}
        
        PROVEN ATS BULLET TEMPLATES & ACTION VERBS AVAILABLE:
{templates_str}

        INSTRUCTIONS:
        1. 'keywords': List specific keywords to add (e.g., "Add 'Contract Negotiation' to Core Competencies").
        2. 'phrasing': Provide a list of objects with 'original' and 'suggested' bullet points. You MUST ground the 'suggested' rewrites using the STAR formula and high-impact action verbs provided above. Every suggestion must include quantifiable metrics, specific scopes, and tangible business outcomes.
        3. 'formatting_tips': 2-3 standard ATS formatting tips.
        
        Do not invent requirements not related to the gaps.
        """


def build_transition_ats_prompt(
    resume_domain: str,
    jd_domain: str,
    gaps: List[str],
    transition_bridge: dict = None
) -> str:
    """Build prompt for cross-domain career transition ATS optimization tips grounded in verified bridge blueprints."""
    bridge_context = ""
    if transition_bridge:
        strengths = ", ".join(transition_bridge.get("transferable_strengths", []))
        certs = ", ".join(transition_bridge.get("bridge_certifications", []))
        advice = transition_bridge.get("strategic_advice", "")
        projects = "; ".join(transition_bridge.get("recommended_projects", []))
        bridge_context = f"""
        VERIFIED CAREER TRANSITION BLUEPRINT ({resume_domain} -> {jd_domain}):
        - Transferable Strengths to Highlight: {strengths}
        - High-Leverage Bridge Credentials: {certs}
        - Resume Repositioning Strategy: {advice}
        - Recommended Proof-of-Skill Projects: {projects}
        """

    return f"""
            Provide specific, actionable Career Transition ATS optimization tips for a candidate moving from {resume_domain} to {jd_domain}.
            Missing technical skills: {', '.join(gaps)}
            {bridge_context}
            Output format exactly:
            1. 'keywords': A list of foundational keywords they should learn and add (e.g., "Add 'Python' to Core Competencies"). Include recommended bridge credentials above.
            2. 'phrasing': A list of objects with 'original' and 'suggested' bullet points demonstrating how to translate {resume_domain} experience into transferable skills for {jd_domain} using the repositioning strategy.
            3. 'formatting_tips': 2-3 standard ATS formatting tips (e.g. use functional resume format, feature bridge credentials).
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
