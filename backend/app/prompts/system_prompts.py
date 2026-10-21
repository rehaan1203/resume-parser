"""Compatibility facade re-exporting prompts from modular prompt files.

This file exists to maintain backward compatibility with legacy callers
while the codebase is transitioned to direct imports from app.prompts.*.
"""

from app.prompts.base import SYSTEM_PROMPT
from app.prompts.analysis import (
    FRICTION_ANALYSIS_PROMPT,
    SAMPLE_ANALYSIS_PROMPT,
)
from app.prompts.roadmap import THIRTY_DAY_ROADMAP_PROMPT as ROADMAP_PROMPT
from app.prompts.ats import ATS_OPTIMIZATION_PROMPT
from app.prompts.career import (
    INTERVIEW_QUESTIONS_PROMPT,
    CAREER_ADVICE_PROMPT,
)
from app.prompts.extraction import DOMAIN_DETECTION_PROMPT

__all__ = [
    "SYSTEM_PROMPT",
    "FRICTION_ANALYSIS_PROMPT",
    "SAMPLE_ANALYSIS_PROMPT",
    "ROADMAP_PROMPT",
    "ATS_OPTIMIZATION_PROMPT",
    "INTERVIEW_QUESTIONS_PROMPT",
    "CAREER_ADVICE_PROMPT",
    "DOMAIN_DETECTION_PROMPT",
]
