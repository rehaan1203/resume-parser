"""Extracts and calculates seniority deterministically."""
import re
import hashlib
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from app.utils.logger import logger
from app.utils.cache_manager import CacheManager
from app.ai.client import GenAIClient
from app.prompts.extraction_prompt import (
    build_candidate_experience_prompt,
    build_jd_experience_prompt,
    build_experience_extraction_prompt,
)

@dataclass
class ExperienceResult:
    """Explicit result of experience extraction."""
    status: str  # resume: 'found' | 'explicit_zero' | 'not_found' | 'error'
                 # jd: 'found' | 'explicit_zero' | 'not_specified' | 'error'
    years: Optional[int]
    source: str  # 'regex' | 'llm'
    evidence: Optional[str] = None

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "decade": 10,
}

NUM_PATTERN = r'(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'

def parse_num(val_str: str) -> Optional[int]:
    """Parse integer or number-word into int."""
    if not val_str:
        return None
    val_str = val_str.lower().strip()
    if val_str.isdigit():
        return int(val_str)
    return NUMBER_WORDS.get(val_str)

def verify_evidence_quote(quote: Optional[str], source_text: str, years: Optional[int]) -> bool:
    """Verify that quote exists in source text (case and whitespace normalized) and contains stated years."""
    if not quote or not source_text:
        return False
    norm_quote = " ".join(quote.lower().split())
    norm_source = " ".join(source_text.lower().split())
    if norm_quote not in norm_source:
        return False

    if years is not None:
        num_str = str(years)
        words_for_year = [w for w, v in NUMBER_WORDS.items() if v == years]
        has_digit = bool(re.search(r'\b' + re.escape(num_str) + r'\b', norm_quote))
        has_word = any(re.search(r'\b' + re.escape(w) + r'\b', norm_quote) for w in words_for_year)
        if not (has_digit or has_word):
            return False

    return True

def extract_candidate_experience(resume_text: str) -> ExperienceResult:
    """
    Extract candidate total experience from resume using high-precision rules.
    Statuses: found, explicit_zero, not_found, error.
    Positive patterns run first and always win over zero wording.
    """
    if not resume_text:
        return ExperienceResult(status="not_found", years=None, source="regex")

    try:
        from app.utils.skill_extractor import COMMON_SKILLS
        skills_set = set(s.lower() for s in COMMON_SKILLS)

        # 1. High-precision positive patterns that state total professional or domain experience
        # Bare "N years" or "N yrs" (e.g. "Python for 3 years", "Led a team for 2 years") is NOT accepted.
        patterns = [
            rf'\b{NUM_PATTERN}\+?\s*years?\'?\s*(?:of\s*)?(?:total\s*|overall\s*|professional\s*|relevant\s*|work\s*|career\s*|industry\s*)?experience\b',
            rf'\bexperience\s*of\s*{NUM_PATTERN}\+?\s*years?\b',
            rf'\b{NUM_PATTERN}\+?\s*years?\'?\s*(?:(?:of\s*)?(?:professional\s*|work\s*)?experience\s+)?as\s+(?:a|an)\s+[a-z]+(?:\s+[a-z]+)?\b',
            rf'\b{NUM_PATTERN}\+?\s*years?\s*in\s+(?:the\s+)?(?:industry|workforce|field|profession|domain)\b',
            rf'\b{NUM_PATTERN}\+?\s*years?\s*(?:in|of)\s+([a-z]+ing|[a-z]+)\b',
            r'\b(?:over\s*a|a|one)\s*decade\s*(?:of\s*)?(?:professional|relevant|work|career)?\s*experience\b',
            r'\b(?:over\s*a|a|one)\s*decade\s*in\s+(?:the\s+)?(?:industry|workforce|field|profession)\b',
            r'\btwo\s*decades\s*(?:of\s*)?(?:professional|relevant|work|career)?\s*experience\b',
        ]

        matches = []
        for p in patterns:
            for m in re.finditer(p, resume_text, re.IGNORECASE):
                after_text = resume_text[m.end():m.end() + 20].lower()
                if re.match(r'^\s*(?:ago\b|old\b|-old\b|-year-old\b)', after_text):
                    continue

                groups = m.groups()
                # Check if this was a domain/gerund pattern with a specific tool/skill
                if len(groups) >= 2 and groups[1]:
                    target_noun = groups[1].lower().strip()
                    if target_noun in skills_set:
                        # Specific technical tool/skill duration (e.g. "5 years in Python") is skill tenure, not total experience
                        continue

                matched_str = m.group(0).lower()
                val = None
                if "decade" in matched_str:
                    val = 20 if "two" in matched_str else 10
                elif groups and groups[0]:
                    val = parse_num(groups[0])

                if val is not None and 0 <= val <= 50 and not (1950 <= val <= 2100):
                    matches.append((val, m.group(0)))

        if matches:
            years_list = [item[0] for item in matches]
            max_years = max(years_list)
            min_years = min(years_list)
            if max_years - min_years > 2:
                logger.info(f"Candidate experience matches differ by >2 years: {years_list}, taking max {max_years}")
            best_match = next(item for item in matches if item[0] == max_years)
            if max_years == 0:
                return ExperienceResult(status="explicit_zero", years=0, source="regex", evidence=best_match[1])
            return ExperienceResult(status="found", years=max_years, source="regex", evidence=best_match[1])

        # 2. Whole-career explicit zero checks (positive matches have already been checked and won)
        explicit_zero_patterns = [
            r'\b(?:0|zero)\+?\s*years?(?:\s*of)?\s*(?:work\s*|professional\s*|career\s*)?experience\b',
            r'\bno\s*prior\s*(?:work\s*|professional\s*|career\s*)?experience\b',
            r'\bno\s*(?:professional|work)\s*experience\b',
            r'\bno\s*experience\s*in\s*(?:the\s*)?workforce\b',
        ]
        for p in explicit_zero_patterns:
            m = re.search(p, resume_text, re.IGNORECASE)
            if m:
                return ExperienceResult(status="explicit_zero", years=0, source="regex", evidence=m.group(0))

        # Hints like "recent graduate", "entry-level", bare "no experience" stay not_found (candidate for LLM)
        return ExperienceResult(status="not_found", years=None, source="regex")

    except Exception as e:
        logger.error(f"Error extracting candidate experience: {e}")
        return ExperienceResult(status="error", years=None, source="regex", evidence=str(e))

async def extract_candidate_experience_with_llm(
    resume_text: str,
    client: Optional[GenAIClient] = None
) -> ExperienceResult:
    """Extract candidate experience with high-precision regex and LLM fallback."""
    regex_res = extract_candidate_experience(resume_text)
    if regex_res.status in ("found", "explicit_zero"):
        return regex_res

    from app.config import settings
    max_chars = getattr(settings, "experience_llm_max_chars", 15000)

    try:
        ai_client = client or GenAIClient()
        prompt = build_candidate_experience_prompt(resume_text, max_chars=max_chars)
        raw_response = await ai_client.generate_structured_content(
            prompt=prompt,
            output_schema={
                "status": "string",
                "years": 0,
                "evidence_quote": "string"
            },
            temperature=0.0
        )
        status = raw_response.get("status")
        years = raw_response.get("years")
        quote = raw_response.get("evidence_quote")

        if status == "found":
            if not isinstance(years, int) or years < 0 or years > 50:
                return ExperienceResult(status="not_found", years=None, source="llm")
            if not verify_evidence_quote(quote, resume_text, years):
                logger.warning(f"Candidate experience quote verification failed: quote={quote!r}, years={years}")
                return ExperienceResult(status="not_found", years=None, source="llm")
            return ExperienceResult(status="found", years=years, source="llm", evidence=quote)

        elif status == "explicit_zero":
            if quote and not verify_evidence_quote(quote, resume_text, 0):
                return ExperienceResult(status="not_found", years=None, source="llm")
            return ExperienceResult(status="explicit_zero", years=0, source="llm", evidence=quote)

        else:
            return ExperienceResult(status="not_found", years=None, source="llm")

    except Exception as e:
        logger.error(f"Candidate experience LLM extraction failed: {e}")
        return ExperienceResult(status="error", years=None, source="llm", evidence=str(e))

def extract_required_experience(jd_text: str) -> ExperienceResult:
    """
    Extract minimum required experience from job description using regex.
    Statuses: found (minimum required), explicit_zero, not_specified, error.
    """
    if not jd_text:
        return ExperienceResult(status="not_specified", years=None, source="regex")

    try:
        jd_lower = jd_text.lower()
        # 1. Check explicit zero indicators
        if re.search(r'\b(?:entry[- ]level|no\s*experience\s*required|freshers?(?:\s*welcome)?)\b', jd_lower):
            return ExperienceResult(status="explicit_zero", years=0, source="regex", evidence="entry-level / no experience required")

        range_zero = re.search(r'\b0\s*(?:-|to)\s*(\d+)\s*years?\b', jd_lower)
        if range_zero:
            return ExperienceResult(status="explicit_zero", years=0, source="regex", evidence=range_zero.group(0))

        # 2. Extract required clauses, skipping preferred/plus/nice to have/ideal/bonus
        clauses = re.split(r'[.;\n]', jd_text)
        required_matches = []

        for clause in clauses:
            clause_lower = clause.lower()
            if any(kw in clause_lower for kw in ["preferred", "plus", "nice to have", "ideal", "bonus"]):
                # Split compound clauses by comma or 'and' to isolate required portions
                subparts = re.split(r'[,;]|\band\b', clause)
                for sub in subparts:
                    sub_lower = sub.lower()
                    if any(kw in sub_lower for kw in ["preferred", "plus", "nice to have", "ideal", "bonus"]):
                        continue
                    _extract_jd_clause(sub, required_matches)
            else:
                _extract_jd_clause(clause, required_matches)

        if required_matches:
            years_list = [item[0] for item in required_matches]
            min_years = min(years_list)
            if len(set(years_list)) > 1:
                logger.info(f"Conflicting required JD experience numbers {years_list}, taking smallest {min_years}")
            best_match = next(item for item in required_matches if item[0] == min_years)
            return ExperienceResult(status="found", years=min_years, source="regex", evidence=best_match[1])

        return ExperienceResult(status="not_specified", years=None, source="regex")

    except Exception as e:
        logger.error(f"Error extracting required JD experience: {e}")
        return ExperienceResult(status="error", years=None, source="regex", evidence=str(e))

async def extract_required_experience_with_llm(
    jd_text: str,
    client: Optional[GenAIClient] = None
) -> ExperienceResult:
    """Extract required experience from JD with LLM fallback and evidence verification."""
    regex_res = extract_required_experience(jd_text)
    if regex_res.status in ("found", "explicit_zero"):
        return regex_res

    from app.config import settings
    max_chars = getattr(settings, "experience_llm_max_chars", 15000)

    try:
        ai_client = client or GenAIClient()
        prompt = build_jd_experience_prompt(jd_text, max_chars=max_chars)
        raw_response = await ai_client.generate_structured_content(
            prompt=prompt,
            output_schema={
                "status": "string",
                "years": 0,
                "evidence_quote": "string"
            },
            temperature=0.0
        )
        status = raw_response.get("status")
        years = raw_response.get("years")
        quote = raw_response.get("evidence_quote")

        if status == "found":
            if not isinstance(years, int) or years < 0 or years > 50:
                return ExperienceResult(status="not_specified", years=None, source="llm")
            if not verify_evidence_quote(quote, jd_text, years):
                logger.warning(f"JD experience quote verification failed: quote={quote!r}, years={years}")
                return ExperienceResult(status="not_specified", years=None, source="llm")
            return ExperienceResult(status="found", years=years, source="llm", evidence=quote)

        elif status == "explicit_zero":
            if quote and not verify_evidence_quote(quote, jd_text, 0):
                return ExperienceResult(status="not_specified", years=None, source="llm")
            return ExperienceResult(status="explicit_zero", years=0, source="llm", evidence=quote)

        else:
            return ExperienceResult(status="not_specified", years=None, source="llm")

    except Exception as e:
        logger.error(f"JD experience LLM extraction failed: {e}")
        return ExperienceResult(status="error", years=None, source="llm", evidence=str(e))

def _extract_jd_clause(text: str, matches: list):
    patterns = [
        rf'\bminimum\s*(?:of)?\s*{NUM_PATTERN}\+?\s*years?\b',
        rf'\bat\s*least\s*{NUM_PATTERN}\+?\s*years?\b',
        rf'\b{NUM_PATTERN}\s*(?:-|to)\s*{NUM_PATTERN}\s*years?\b',
        rf'\b{NUM_PATTERN}\+?\s*years?\'?\s*(?:of\s*)?experience\b',
        rf'\b{NUM_PATTERN}\+?\s*yrs?\s*(?:exp)?\b',
        rf'\b{NUM_PATTERN}\+\s*years?\b',
    ]
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            after_text = text[m.end():m.end() + 20].lower()
            if re.match(r'^\s*(?:ago\b|old\b|-old\b|-year-old\b)', after_text):
                continue
            groups = m.groups()
            val = None
            if len(groups) >= 2 and groups[0] and groups[1] and ('-' in m.group(0) or 'to' in m.group(0)):
                val = parse_num(groups[0])
            elif groups and groups[0]:
                val = parse_num(groups[0])

            if val is not None and 0 <= val <= 50 and not (1950 <= val <= 2100):
                matches.append((val, m.group(0)))

async def extract_years_experience(text: str) -> int:
    """
    Legacy wrapper extracting years of experience.
    Preserves existing signature and behavior for orchestrator until Stage 2 migration.
    """
    if not text:
        return 0

    patterns = [
        r'(\d+)\+?\s*years?\s*of\s*experience',
        r'(\d+)\s*\+\s*years?\s*experience',
        r'(\d+)\+?\s*yrs?\s*exp',
        r'minimum\s*of\s*(\d+)\s*years',
        r'(\d+)(?:\s*to\s*\d+)?\s*years',
    ]

    years_found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            after_text = text[match.end():match.end() + 20].lower()
            if re.match(r'^\s*(?:ago\b|old\b|-old\b|-year-old\b)', after_text):
                continue
            try:
                val = int(match.group(1))
                if val > 50 or (1950 <= val <= 2100):
                    continue
                years_found.append(val)
            except ValueError:
                pass

    if years_found:
        return max(years_found)

    # --- LLM Fallback (Regex Failed) ---
    logger.warning("Regex extraction for years of experience failed. Falling back to LLM.")
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_key = f"exp_extract:{text_hash}"
    cache_manager = CacheManager()

    cached_years = await cache_manager.get(cache_key)
    if cached_years is not None:
        logger.info(f"Retrieved extracted years from cache: {cached_years}")
        return int(cached_years)

    try:
        client = GenAIClient()
        prompt = build_experience_extraction_prompt(text)
        response = await client.generate_structured_content(
            prompt=prompt,
            output_schema={"years": 0}
        )
        years = response.get("years", 0)
        await cache_manager.set(cache_key, years, ttl=86400)
        logger.info(f"LLM successfully extracted {years} years of experience.")
        return years
    except Exception as e:
        logger.error(f"LLM fallback for experience extraction failed: {e}")
        return 0
