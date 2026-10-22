"""Calculates the matching scores deterministically."""

def calculate_skills_score(matching_skills: int, total_jd_skills: int) -> int:
    """Calculate skill score out of 100."""
    if total_jd_skills == 0:
        return 0
    return int((matching_skills / total_jd_skills) * 100)
    
def calculate_overall_score(skills_score: int, seniority_score: int) -> int:
    """Calculate overall score based on 60/40 weighting."""
    score = int((skills_score * 0.6) + (seniority_score * 0.4))
    # Clamp to max 100
    return min(max(score, 0), 100)
