"""Calculates the matching scores deterministically."""

from typing import Optional, Dict, Any, List
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

def calculate_open_domain_weighted_score(
    requirements: List[Dict[str, Any]],
    matches: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate weighted open-domain requirement score (D4 formula).
    Score = (sum(w_i * c_i) / sum(w_i)) * 100
    Weights: must_have = 1.0, preferred = 0.5, bonus = 0.25.
    Credits: match = 1.0, partial = 0.5, missing = 0.0.
    """
    if not requirements:
        return {
            "overall_score": 0,
            "weighted_score": 0.0,
            "total_weight": 0.0,
            "earned_weight": 0.0,
            "category_breakdown": {}
        }

    tier_weights = {"must_have": 1.0, "preferred": 0.5, "bonus": 0.25}
    total_w = 0.0
    earned_w = 0.0
    cat_breakdown: Dict[str, Dict[str, Any]] = {}

    match_dict = {}
    for m in matches:
        req_name = m.get("requirement_name", "").lower().strip()
        match_dict[req_name] = m

    for req in requirements:
        name = req.get("name", "").lower().strip()
        category = req.get("category", "skill")
        tier = req.get("importance", "must_have")
        w = tier_weights.get(tier, 1.0)
        total_w += w

        m = match_dict.get(name, {})
        credit = float(m.get("credit", 0.0))
        earned = w * credit
        earned_w += earned

        if category not in cat_breakdown:
            cat_breakdown[category] = {"total_weight": 0.0, "earned_weight": 0.0, "count": 0, "matches": 0}
        cat_breakdown[category]["total_weight"] += w
        cat_breakdown[category]["earned_weight"] += earned
        cat_breakdown[category]["count"] += 1
        if credit >= 0.5:
            cat_breakdown[category]["matches"] += 1

    final_score = (earned_w / total_w) * 100.0 if total_w > 0 else 0.0
    final_score_clamped = min(max(final_score, 0.0), 100.0)

    for cat, data in cat_breakdown.items():
        data["score"] = round((data["earned_weight"] / data["total_weight"]) * 100.0, 1) if data["total_weight"] > 0 else 0.0

    return {
        "overall_score": int(round(final_score_clamped)),
        "weighted_score": round(final_score_clamped, 2),
        "total_weight": round(total_w, 2),
        "earned_weight": round(earned_w, 2),
        "category_breakdown": cat_breakdown
    }
