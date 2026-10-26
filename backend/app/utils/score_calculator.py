"""Calculates the matching scores deterministically."""

from typing import Optional
from app.config import settings

def calculate_skills_score(matching_skills: int, total_jd_skills: int) -> int:
    """Calculate skill score out of 100."""
    if total_jd_skills == 0:
        return 0
    return int((matching_skills / total_jd_skills) * 100)
    
def calculate_overall_score(
    skills_score: int,
    seniority_score: Optional[int],
    skills_weight: Optional[float] = None,
    seniority_weight: Optional[float] = None
) -> int:
    """
    Calculate overall score with configurable weighting.
    When seniority is not assessed (seniority_score is None),
    renormalizes weight entirely to skills (skills only).
    """
    if seniority_score is None:
        return min(max(int(skills_score), 0), 100)

    w_skills = skills_weight if skills_weight is not None else getattr(settings, "skills_weight", 0.6)
    w_seniority = seniority_weight if seniority_weight is not None else getattr(settings, "seniority_weight", 0.4)

    total_w = w_skills + w_seniority
    if total_w <= 0:
        total_w = 1.0

    score = int((skills_score * (w_skills / total_w)) + (seniority_score * (w_seniority / total_w)))
    return min(max(score, 0), 100)
