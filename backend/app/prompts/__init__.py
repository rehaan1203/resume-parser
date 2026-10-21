"""Public interface for the prompts package."""
from app.prompts.base import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION, STRICT_JSON_INSTRUCTION
from app.prompts.analysis import (
    build_executive_summary_prompt,
    build_mismatch_prompt,
    FRICTION_ANALYSIS_PROMPT,
    SAMPLE_ANALYSIS_PROMPT,
    EXECUTIVE_SUMMARY_PROMPT_VERSION,
    DOMAIN_MISMATCH_PROMPT_VERSION,
    FRICTION_ANALYSIS_PROMPT_VERSION,
    SAMPLE_ANALYSIS_PROMPT_VERSION
)
from app.prompts.roadmap import (
    build_upskill_roadmap_prompt,
    build_transition_roadmap_prompt,
    THIRTY_DAY_ROADMAP_PROMPT,
    UPSKILL_ROADMAP_PROMPT_VERSION,
    TRANSITION_ROADMAP_PROMPT_VERSION,
    THIRTY_DAY_ROADMAP_PROMPT_VERSION
)
from app.prompts.ats import (
    build_standard_ats_prompt,
    build_transition_ats_prompt,
    build_transition_tips_prompt,
    ATS_OPTIMIZATION_PROMPT,
    STANDARD_ATS_PROMPT_VERSION,
    TRANSITION_ATS_PROMPT_VERSION,
    TRANSITION_TIPS_PROMPT_VERSION,
    ATS_OPTIMIZATION_PROMPT_VERSION
)
from app.prompts.seniority import (
    build_seniority_alignment_prompt,
    SENIORITY_ALIGNMENT_PROMPT_VERSION
)
from app.prompts.extraction import (
    build_experience_extraction_prompt,
    DOMAIN_DETECTION_PROMPT,
    EXPERIENCE_EXTRACTION_PROMPT_VERSION,
    DOMAIN_DETECTION_PROMPT_VERSION
)
from app.prompts.career import (
    INTERVIEW_QUESTIONS_PROMPT,
    CAREER_ADVICE_PROMPT,
    INTERVIEW_QUESTIONS_PROMPT_VERSION,
    CAREER_ADVICE_PROMPT_VERSION
)

__all__ = [
    # Base
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_VERSION",
    "STRICT_JSON_INSTRUCTION",
    # Analysis
    "build_executive_summary_prompt",
    "build_mismatch_prompt",
    "FRICTION_ANALYSIS_PROMPT",
    "SAMPLE_ANALYSIS_PROMPT",
    "EXECUTIVE_SUMMARY_PROMPT_VERSION",
    "DOMAIN_MISMATCH_PROMPT_VERSION",
    "FRICTION_ANALYSIS_PROMPT_VERSION",
    "SAMPLE_ANALYSIS_PROMPT_VERSION",
    # Roadmap
    "build_upskill_roadmap_prompt",
    "build_transition_roadmap_prompt",
    "THIRTY_DAY_ROADMAP_PROMPT",
    "UPSKILL_ROADMAP_PROMPT_VERSION",
    "TRANSITION_ROADMAP_PROMPT_VERSION",
    "THIRTY_DAY_ROADMAP_PROMPT_VERSION",
    # ATS
    "build_standard_ats_prompt",
    "build_transition_ats_prompt",
    "build_transition_tips_prompt",
    "ATS_OPTIMIZATION_PROMPT",
    "STANDARD_ATS_PROMPT_VERSION",
    "TRANSITION_ATS_PROMPT_VERSION",
    "TRANSITION_TIPS_PROMPT_VERSION",
    "ATS_OPTIMIZATION_PROMPT_VERSION",
    # Seniority
    "build_seniority_alignment_prompt",
    "SENIORITY_ALIGNMENT_PROMPT_VERSION",
    # Extraction
    "build_experience_extraction_prompt",
    "DOMAIN_DETECTION_PROMPT",
    "EXPERIENCE_EXTRACTION_PROMPT_VERSION",
    "DOMAIN_DETECTION_PROMPT_VERSION",
    # Career
    "INTERVIEW_QUESTIONS_PROMPT",
    "CAREER_ADVICE_PROMPT",
    "INTERVIEW_QUESTIONS_PROMPT_VERSION",
    "CAREER_ADVICE_PROMPT_VERSION",
]
