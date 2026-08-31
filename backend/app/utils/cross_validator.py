"""Validates the output payload for consistency."""
from typing import Dict, Any

def validate_and_override(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures deterministic consistency rules are met across the final response."""
    
    score = payload.get("overall_score", 0)
    seniority = payload.get("seniority_analysis", {})
    friction = payload.get("friction_points", [])
    gaps = payload.get("skill_gaps", [])
    roadmap = payload.get("roadmap")
    strengths = payload.get("strengths", [])
    
    overrides_applied = []
    
    # 1. Score vs Seniority
    seniority_gap = seniority.get("gap", 0)
    if isinstance(seniority_gap, (int, float)):
        if seniority_gap >= 3 and score > 80:
            original_score = score
            score = 80
            payload["overall_score"] = score
            overrides_applied.append(f"score_clamped_from_{original_score}_to_80")
        
    # 2. Score vs Friction Points
    if score < 100 and not friction:
        friction.append({
            "category": "general",
            "severity": "info",
            "description": "Minor gaps found in overall profile alignment.",
            "suggestion": "Review the full job description for nuanced requirements."
        })
        payload["friction_points"] = friction
        overrides_applied.append("added_generic_friction_point")
        
    # 3. Roadmap vs Gaps (if not perfect)
    if gaps and not roadmap and score < 95:
        payload["roadmap"] = {
            "type": "standard_upskill",
            "title": "📚 Standard Upskill",
            "content": {"message": "Focus on closing your identified skill gaps."}
        }
        overrides_applied.append("added_default_roadmap")
        
    # 4. Strengths vs Gaps
    # If a skill is in skill_gaps, it CANNOT be in strengths
    strengths_to_keep = []
    for s in strengths:
        if s not in gaps:
            strengths_to_keep.append(s)
        else:
            overrides_applied.append(f"removed_conflict_{s}_from_strengths")
    payload["strengths"] = strengths_to_keep
    
    # 5. Perfect Match Case
    if score >= 95:
        payload["roadmap"] = None
        payload["friction_points"] = []
        payload["perfect_match"] = True
        overrides_applied.append("applied_perfect_match_rules")
        
    payload["cross_validation_status"] = {
        "passed": True,
        "checks_performed": ["score_vs_seniority", "score_vs_friction", "roadmap_vs_gaps", "strengths_vs_gaps", "perfect_match"],
        "overrides_applied": overrides_applied
    }
    
    return payload
