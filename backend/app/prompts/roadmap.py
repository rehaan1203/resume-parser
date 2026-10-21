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

