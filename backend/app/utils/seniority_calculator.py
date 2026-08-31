"""Calculates seniority match and level."""
from typing import Dict, Any

def get_seniority_level(years: int) -> str:
    """Map years of experience to a level name."""
    if years <= 1:
        return "Entry"
    elif years <= 4:
        return "Mid"
    elif years <= 7:
        return "Senior"
    elif years <= 10:
        return "Lead"
    else:
        return "Executive"

def calculate_seniority_score_and_gap(candidate_years: int, required_years: int) -> Dict[str, Any]:
    """Calculate gap and score based on difference."""
    gap = required_years - candidate_years
    
    if gap <= 0:
        score = 100
        gap = 0
    elif gap == 1:
        score = 80
    elif gap == 2:
        score = 60
    elif gap == 3:
        score = 40
    else:
        score = 20
        
    return {
        "years_experience": candidate_years,
        "required_years": required_years,
        "your_level": get_seniority_level(candidate_years),
        "required_level": get_seniority_level(required_years),
        "seniority_score": score,
        "gap": gap
    }
