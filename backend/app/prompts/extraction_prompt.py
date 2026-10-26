"""Prompts and builder functions for candidate and JD experience extraction fallbacks."""

EXPERIENCE_EXTRACTION_PROMPT_VERSION = "v2"

def build_candidate_experience_prompt(text: str, max_chars: int = 15000) -> str:
    """Build prompt for LLM fallback extraction of candidate total professional experience."""
    return f"""You are an expert resume parser extracting candidate total professional experience.
Extract ONLY what the text EXPLICITLY states about total professional experience.

Rules:
- Do NOT compute or calculate from employment dates or graduation dates.
- Do NOT count education degrees, internships, skill-specific durations, or 'ago' phrases.
- Return status 'found' with the exact integer 'years', the exact 'evidence_quote' from the text, and classify the 'scope'.
- Return status 'explicit_zero' with years 0, evidence_quote, and scope 'total_career' if the text unambiguously states no prior experience.
- Return status 'not_found' with null years, null evidence_quote, and null scope if total professional experience is not explicitly stated.

Scope classification:
- 'total_career': Overall or total career tenure across a profession or industry (e.g. '10 years of experience', '10+ years in nursing', 'a decade in medicine', '7 years in sales', '5 years as an engineer').
- 'skill_or_tool': Experience with a specific software, tool, language, or single skill (e.g. '5 years of Python', '3 years of React').
- 'education': Time spent in school, college, or university degree (e.g. '4 years in college', '3 years of study').
- 'location_or_employer': Time living in a location or time at a single employer/company (e.g. '5 years in London', '4 years at Google').
- 'other': Age ('30 years old'), elapsed time ('graduated 5 years ago'), or other non-career durations.

Return ONLY a JSON object matching this schema:
{{
  "status": "found" | "explicit_zero" | "not_found",
  "years": integer or null,
  "evidence_quote": string or null,
  "scope": "total_career" | "skill_or_tool" | "education" | "location_or_employer" | "other" | null
}}

Text:
{text[:max_chars]}"""

def build_jd_experience_prompt(text: str, max_chars: int = 15000) -> str:
    """Build prompt for LLM fallback extraction of minimum required experience from job description."""
    return f"""You are an expert job description parser extracting minimum required experience.
Extract ONLY the MINIMUM required professional experience for the role.

Rules:
- Ignore preferred, bonus, nice-to-have, or ideal experience figures.
- For ranges (e.g. 3-5 years), extract the minimum (3).
- Return status 'found' with minimum required integer 'years' and the exact 'evidence_quote' from the text.
- Return status 'explicit_zero' with years 0 and evidence_quote if entry-level or no experience required.
- Return status 'not_found' with null years and null evidence_quote if no experience requirement is stated.

Return ONLY a JSON object matching this schema:
{{
  "status": "found" | "explicit_zero" | "not_found",
  "years": integer or null,
  "evidence_quote": string or null
}}

Text:
{text[:max_chars]}"""

