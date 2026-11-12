"""Calculates seniority match and level deterministically."""
from typing import Dict, Any, Optional, Tuple, Union

def get_seniority_level(years: Optional[Union[int, float]]) -> Optional[str]:
    """Map years of experience (supporting fractional years like 1.5, 1.8) to a level name."""
    if years is None:
        return None
    if years < 2:
        return "Entry"
    elif years <= 4:
        return "Mid"
    elif years <= 7:
        return "Senior"
    elif years <= 10:
        return "Lead"
    else:
        return "Executive"

def _normalize_exp_input(val: Any, default_status: str) -> Tuple[str, Optional[Union[int, float]], Optional[str], Optional[str]]:
    """Normalize input (ExperienceResult, int, float, dict, or None) to (status, years, source, evidence)."""
    if val is None:
        return default_status, None, None, None
    if hasattr(val, "status") and hasattr(val, "years"):
        return val.status, val.years, getattr(val, "source", None), getattr(val, "evidence", None)
    if isinstance(val, dict):
        return val.get("status", default_status), val.get("years"), val.get("source"), val.get("evidence")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if val == 0:
            return "explicit_zero", 0, "regex", "0 years"
        return "found", val, "regex", f"{val} years"
    return default_status, None, None, None

def calculate_seniority_score_and_gap(
    candidate_exp: Any,
    required_exp: Any
) -> Dict[str, Any]:
    """
    Calculate seniority score, gap, status, and assessment details.
    
    Statuses:
    - match: candidate meets/exceeds requirement (gap <= 0) or JD explicit_zero
    - minor_gap: candidate has 1 or 2 years gap
    - significant_gap: candidate has >= 3 years gap (or candidate explicit_zero vs required N)
    - unconfirmed: candidate experience not_found or error (seniority not assessed)
    - not_specified: JD experience not_specified or error (seniority not assessed)
    """
    cand_status, cand_years, cand_source, cand_evidence = _normalize_exp_input(candidate_exp, "not_found")
    jd_status, jd_years, jd_source, jd_evidence = _normalize_exp_input(required_exp, "not_specified")

    # 1. JD not specified or error -> not_specified
    if jd_status in ("not_specified", "error"):
        reason = "Job description does not specify required experience." if jd_status == "not_specified" else "Error extracting required experience from job description."
        return {
            "status": "not_specified",
            "seniority_status": "not_specified",
            "seniority_assessed": False,
            "seniority_score": None,
            "seniority_match": None,
            "gap": None,
            "years_experience": cand_years,
            "required_years": None,
            "your_level": get_seniority_level(cand_years),
            "required_level": None,
            "seniority_reason": reason,
            "badge": "⚪ NOT SPECIFIED",
            "evidence": cand_evidence,
            "source": cand_source,
            "candidate_source": cand_source,
            "candidate_evidence": cand_evidence,
            "candidateSource": cand_source,
            "candidateEvidence": cand_evidence,
            "jd_source": jd_source,
            "jd_evidence": jd_evidence
        }

    # 2. Candidate unconfirmed or error -> unconfirmed
    if cand_status in ("not_found", "error"):
        reason = "Candidate total experience is not explicitly stated in resume (unconfirmed)." if cand_status == "not_found" else "Error extracting candidate experience from resume."
        return {
            "status": "unconfirmed",
            "seniority_status": "unconfirmed",
            "seniority_assessed": False,
            "seniority_score": None,
            "seniority_match": None,
            "gap": None,
            "years_experience": None,
            "required_years": jd_years,
            "your_level": None,
            "required_level": get_seniority_level(jd_years),
            "seniority_reason": reason,
            "badge": "⚪ UNCONFIRMED",
            "evidence": cand_evidence,
            "source": cand_source,
            "candidate_source": cand_source,
            "candidate_evidence": cand_evidence,
            "candidateSource": cand_source,
            "candidateEvidence": cand_evidence,
            "jd_source": jd_source,
            "jd_evidence": jd_evidence
        }

    # 3. JD explicit zero gives match
    if jd_status == "explicit_zero":
        c_years = cand_years if cand_years is not None else 0
        return {
            "status": "match",
            "seniority_status": "match",
            "seniority_assessed": True,
            "seniority_score": 100,
            "seniority_match": 100,
            "gap": 0,
            "years_experience": c_years,
            "required_years": 0,
            "your_level": get_seniority_level(c_years),
            "required_level": "Entry",
            "seniority_reason": "Entry-level position; no prior experience required.",
            "badge": "✅ PERFECT MATCH",
            "evidence": cand_evidence,
            "source": cand_source,
            "candidate_source": cand_source,
            "candidate_evidence": cand_evidence,
            "candidateSource": cand_source,
            "candidateEvidence": cand_evidence,
            "jd_source": jd_source,
            "jd_evidence": jd_evidence
        }

    # 4. Both candidate and JD have stated experience (supports whole & 1-decimal fractional years e.g. 1.5, 1.8)
    c_years = cand_years if cand_years is not None else 0
    r_years = jd_years if jd_years is not None else 0
    raw_gap = round(r_years - c_years, 1)
    gap: Union[int, float] = int(round(raw_gap)) if abs(raw_gap - round(raw_gap)) < 0.05 else raw_gap

    if gap <= 0:
        status = "match"
        score = 100
        gap = 0
        badge = "✅ PERFECT MATCH"
        reason = "Candidate meets or exceeds required years of experience."
    elif gap <= 2:
        status = "minor_gap"
        score = int(round(100 - (gap * 20)))
        badge = "🟡 MINOR GAP"
        reason = f"Candidate has a minor experience gap of {gap} year{'s' if gap != 1 else ''}."
    else:
        status = "significant_gap"
        score = 40 if gap <= 3 else 20
        badge = "🔴 SIGNIFICANT GAP"
        reason = f"Candidate has a significant experience gap of {gap} years."

    return {
        "status": status,
        "seniority_status": status,
        "seniority_assessed": True,
        "seniority_score": score,
        "seniority_match": score,
        "gap": gap,
        "years_experience": c_years,
        "required_years": r_years,
        "your_level": get_seniority_level(c_years),
        "required_level": get_seniority_level(r_years),
        "seniority_reason": reason,
        "badge": badge,
        "evidence": cand_evidence,
        "source": cand_source,
        "candidate_source": cand_source,
        "candidate_evidence": cand_evidence,
        "candidateSource": cand_source,
        "candidateEvidence": cand_evidence,
        "jd_source": jd_source,
        "jd_evidence": jd_evidence
    }
