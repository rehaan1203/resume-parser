"""Open-domain requirement extraction prompts (D4 Specification)."""

OPEN_DOMAIN_REQUIREMENTS_PROMPT_VERSION = "v2"


def _prepare_core_text(text: str, doc_type: str, max_chars: int) -> str:
    """Preserve critical sections across long documents without abrupt bottom truncation."""
    if not text or len(text) <= max_chars:
        return text or ""
    try:
        from app.utils.document_chunker import extract_core_sections
        return extract_core_sections(text, doc_type=doc_type, max_chars=max_chars)
    except Exception:
        return text[:max_chars]


def build_open_domain_jd_prompt(jd_text: str, max_chars: int = 12000) -> str:
    """Build prompt to extract open-domain role/industry and discrete qualification requirements from any JD."""
    prepared_jd = _prepare_core_text(jd_text, doc_type="jd", max_chars=max_chars)
    return f"""You are an expert universal job analyst across ALL industries (software, AI/ML, cybersecurity, healthcare, legal, finance, skilled trades, education, operations, design, etc.).
Infer the exact professional domain/specialization of this job description and extract all concrete qualification requirements (do not limit yourself to any preset skill list).

REQUIREMENT CATEGORIES:
1. 'skill': Concrete technical, clinical, legal, analytical, artisan, or domain capabilities (e.g., LangChain, RAG, SIEM, Patient Triage, Contract Drafting, CNC Operation).
2. 'domain_experience': Industry immersion or specialized background (e.g., Acute Care Nursing, FinTech, Criminal Defense, Commercial HVAC).
3. 'credential': Certifications, government licenses, bar admissions, or accreditations (e.g., RN License, BLS, ACLS, EPA 608 Universal, New York Bar, PMP, CISSP).
4. 'education': Required degrees or academic levels (e.g., BSN in Nursing, JD, BS in Computer Science, High School Diploma).
5. 'leadership': Team oversight, mentorship, or practice management (e.g., Charge Nurse, Lead Architect, Managing Attorney, Foreman).
6. 'tool': Specific software, platforms, frameworks, medical devices, hardware, or machinery (e.g., Epic EHR, LexisNexis, Docker, Kubernetes, PyTorch, SAP, CrowdStrike).

CRITICAL RULE FOR EXPERIENCE DURATIONS:
- If a requirement specifies a duration (e.g. "5 years in ICU"), categorize as 'domain_experience' or 'skill'.
- Do NOT categorize plain qualitative statements (e.g., "clean driving record", "pass background check") as experience duration; tag them as 'credential' or 'skill'.

IMPORTANCE TIERS:
- 'must_have': Required, mandatory, essential, minimum requirements (weight 1.0).
- 'preferred': Strongly preferred, desired, or plus (weight 0.5).
- 'bonus': Nice-to-have, optional, or advantageous (weight 0.25).

OUTPUT SCHEMA:
Return a single JSON object with keys "domain" and "requirements":
{{
  "domain": "Concise specialization label (e.g., AI Engineering, Cybersecurity, Software Engineering, Clinical Nursing, Supply Chain)",
  "requirements": [
    {{
      "name": "Canonical Requirement Name (concise 1-4 words)",
      "category": "skill" | "domain_experience" | "credential" | "education" | "leadership" | "tool",
      "importance": "must_have" | "preferred" | "bonus",
      "raw_text": "Exact or near-exact clause from JD"
    }}
  ]
}}

JOB DESCRIPTION:
{prepared_jd}"""

def build_open_domain_matching_prompt(
    requirements_json_str: str,
    resume_text: str,
    max_chars: int = 12000
) -> str:
    """Build prompt to evaluate candidate fulfillment of extracted requirements."""
    prepared_resume = _prepare_core_text(resume_text, doc_type="resume", max_chars=max_chars)
    return f"""You are an objective hiring auditor. Evaluate whether the candidate's resume satisfies each of the extracted job requirements.

CREDIT RULES:
- credit 1.0 (status 'matched'): Resume explicitly proves candidate meets or exceeds this requirement.
- credit 0.5 (status 'partial'): Candidate demonstrates closely related, transferable, or partial capability (e.g., California Bar for a US general legal role, or Vue for React, or telemetry nurse for ICU).
- credit 0.0 (status 'missing'): Resume has no demonstrable evidence for this requirement.

EVIDENCE RULES:
- 'evidence_quote': Must be an exact, verbatim quote from the candidate's resume supporting the credit. If missing, evidence_quote must be null.

OUTPUT SCHEMA:
Return a JSON object with key "matches":
{{
  "matches": [
    {{
      "requirement_name": "Requirement Name",
      "category": "skill" | "domain_experience" | "credential" | "education" | "leadership" | "tool",
      "importance": "must_have" | "preferred" | "bonus",
      "credit": 1.0 | 0.5 | 0.0,
      "status": "matched" | "partial" | "missing",
      "evidence_quote": "Verbatim quote from resume" or null
    }}
  ]
}}

REQUIREMENTS TO EVALUATE:
{requirements_json_str}

CANDIDATE RESUME:
{prepared_resume}"""

