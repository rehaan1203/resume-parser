"""Prompts and builder functions for learning and career transition roadmaps."""
from typing import List

UPSKILL_ROADMAP_PROMPT_VERSION = "v1"
TRANSITION_ROADMAP_PROMPT_VERSION = "v1"
THIRTY_DAY_ROADMAP_PROMPT_VERSION = "v1"


def get_roadmap_weeks_count(gap_type: str = "standard_upskill") -> int:
    """Return the duration in weeks for a given gap type."""
    if gap_type == "mini_upskill":
        return 1
    elif gap_type == "short_upskill":
        return 2
    elif gap_type == "extended_upskill":
        return 8
    elif gap_type == "career_change":
        return 12
    return 4


def build_upskill_roadmap_prompt(gaps: List[str], gap_type: str = "standard_upskill") -> str:
    """Build prompt for generating a structured upskilling roadmap."""
    weeks_count = get_roadmap_weeks_count(gap_type)

    return f"""
        Generate a highly structured, non-repeating learning roadmap for a candidate missing these skills: {', '.join(gaps)}.
        The roadmap must be EXACTLY {weeks_count} weeks long. Every single day in those weeks must have unique content and at least one real-world resource link (e.g., Coursera, YouTube, official docs).
        
        CRITICAL TOKEN LIMIT: To prevent truncation for long {weeks_count}-week roadmaps, you MUST keep every 'action' description concise (under 20 words) and provide 1-2 highly relevant URLs per day. Do not add any extra commentary.
        
        Output format:
        - type: "{gap_type}"
        - title: "Upskill Roadmap ({weeks_count} Weeks)"
        - weeks: List of week objects, each containing:
            - week: week number
            - focus: week theme
            - days: List of 7 day objects (for that week), each containing:
                - day: absolute day number (1, 2, ..., {weeks_count * 7})
                - action: what to do
                - resources: list of URLs
                - estimated_time: string (e.g., "2 hours")
        """


def build_rag_upskill_roadmap_prompt(
    gaps: List[str],
    gap_type: str = "standard_upskill",
    verified_resources: List[dict] = None,
    target_role: str = "",
) -> str:
    """Build prompt for generating an upskilling roadmap grounded in verified catalog resources."""
    weeks_count = get_roadmap_weeks_count(gap_type)
    role_ctx = f" targeting '{target_role}'" if target_role else ""

    if verified_resources:
        resources_lines = []
        # Cap to top 8 resources and truncate descriptions to 100 chars to protect token budget
        for r in verified_resources[:8]:
            title = r.get("title", "")
            url = r.get("url", "")
            rtype = r.get("type", r.get("resource_type", "Resource"))
            raw_desc = r.get("description", "")
            desc = (raw_desc[:97] + "...") if len(raw_desc) > 100 else raw_desc
            resources_lines.append(f"- [{title}]({url}) ({rtype}: {desc})")
        resources_text = "\n".join(resources_lines)
    else:
        resources_text = "None provided. Use reputable, working official documentation or top learning platform URLs."

    return f"""
        Generate a highly structured, non-repeating learning roadmap for a candidate{role_ctx} missing these skills: {', '.join(gaps)}.
        The roadmap must be EXACTLY {weeks_count} weeks long. Every single day in those weeks must have unique content and at least one real-world resource link.

        VERIFIED LEARNING RESOURCES AVAILABLE:
{resources_text}

        MANDATORY URL USAGE INSTRUCTIONS:
        1. Stay strictly aligned with the target stack and missing skills ({', '.join(gaps)}). NEVER introduce competing cloud vendors (e.g., do NOT suggest AWS services/courses or compare with AWS when target skills are Azure or GCP).
        2. Prioritize and draw from the verified resources listed above whenever applicable for a day's topic. Use their exact URLs, and vary resources across days rather than repeating one generic link back-to-back.
        3. DO NOT hallucinate fake or placeholder URLs (such as 'youtube.com/watch?v=12345' or 'arxiv.org/abs/12345').
        4. If no verified resource matches a specific day's topic, use real, working official documentation URLs (e.g. docs.python.org, learn.microsoft.com, langchain-ai.github.io, official vendor portals).

        CRITICAL TOKEN LIMIT: To prevent truncation for long {weeks_count}-week roadmaps, you MUST keep every 'action' description concise (under 20 words) and provide 1-2 highly relevant URLs per day. Do not add any extra commentary.
        
        Output format:
        - type: "{gap_type}"
        - title: "Upskill Roadmap ({weeks_count} Weeks)"
        - weeks: List of week objects, each containing:
            - week: week number
            - focus: week theme
            - days: List of 7 day objects (for that week), each containing:
                - day: absolute day number (1, 2, ..., {weeks_count * 7})
                - action: what to do
                - resources: list of URLs
                - estimated_time: string (e.g., "2 hours")
        """


def build_transition_roadmap_prompt(
    resume_domain: str,
    jd_domain: str,
    resume: str,
    jd: str
) -> str:
    """Build prompt for a full 12-18 month career transition roadmap."""
    return f"""
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


THIRTY_DAY_ROADMAP_PROMPT = """Create a {days}-day learning roadmap to close these skill gaps:

SKILL GAPS:
{gaps}

STRENGTHS (leverage these):
{strengths}

Generate a structured roadmap with:
- Weekly themes (4 weeks)
- Daily actions (1 per day, achievable in 30-60 minutes)
- Specific resources (courses, books, GitHub repos, tools with actual URLs)

The roadmap should be realistic, actionable, and build from fundamentals to advanced concepts.

Return ONLY this JSON object:
{{
  "roadmap": [
    {{"week": 1, "day": 1, "action": "Complete Python basics course", "resources": ["https://..."], "completed": false}},
    ...
  ]
}}

Ensure all 30 days are covered (weeks 1-4, days 1-30)."""

