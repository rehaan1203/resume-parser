"""Generates friction points, strengths, and gaps deterministically."""
from typing import List, Dict, Any

def generate_friction_and_strengths(
    matching_skills: List[str],
    missing_skills: List[str],
    seniority_gap: int,
    candidate_years: int,
    required_years: int,
    domain_analysis: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate friction points, strengths, and skill gaps deterministically."""
    
    friction_points = []
    
    if domain_analysis:
        is_mismatch = domain_analysis.get("is_mismatch", False)
        is_unknown = domain_analysis.get("is_unknown", False)
        resume_domain = domain_analysis.get("resume_domain", "unknown").replace("_", " ").title()
        jd_domain = domain_analysis.get("jd_domain", "unknown").replace("_", " ").title()
        
        if is_unknown:
            friction_points.append({
                "category": "domain_unclear",
                "severity": "warning",
                "description": "Could not clearly detect your domain. Please ensure your resume clearly mentions your industry.",
                "suggestion": "Add specific keywords about your industry (e.g., 'Law', 'Healthcare', 'Technology')."
            })
        elif is_mismatch:
            friction_points.append({
                "category": "domain_mismatch",
                "severity": "critical",
                "description": f"Your resume is in {resume_domain} domain, but this role requires {jd_domain}.",
                "suggestion": "This role requires completely different skills. Consider roles in your domain or a career transition."
            })
    
    # 1. Experience Friction
    if seniority_gap > 0:
        friction_points.append({
            "category": "experience",
            "severity": "high" if seniority_gap >= 3 else "warning",
            "description": f"You have {candidate_years} years of experience, but this role requires {required_years}+ years.",
            "suggestion": f"Highlight transferable skills to bridge the {seniority_gap}-year gap."
        })
        
    # 2. Skill Friction
    if missing_skills:
        friction_points.append({
            "category": "skills",
            "severity": "warning",
            "description": f"Missing key skills: {', '.join(missing_skills[:3])}{' and others' if len(missing_skills) > 3 else ''}.",
            "suggestion": f"Consider certifications or projects involving these skills."
        })
        
    # Strengths are exactly the matching skills
    strengths = matching_skills.copy()
    
    # Gaps are exactly the missing skills
    skill_gaps = missing_skills.copy()
    
    return {
        "friction_points": friction_points,
        "strengths": strengths,
        "skill_gaps": skill_gaps
    }
