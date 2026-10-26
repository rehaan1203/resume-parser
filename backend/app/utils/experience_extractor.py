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
    EXPERIENCE_EXTRACTION_PROMPT_VERSION,
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

ROLE_STOPLIST = {
    "student", "undergraduate", "grad", "graduate",
    "intern", "internship", "trainee", "apprentice",
    "fellow", "phd", "candidate"
}

def verify_evidence_quote(
    quote: Optional[str],
    source_text: str,
    years: Optional[int],
    mode: str = "candidate",
    scope: Optional[str] = None
) -> bool:
    """
    Verify that an LLM-extracted evidence quote actually supports the claim.
    Rules:
    - Quote must exist verbatim (normalized) in the source text.
    - Stated years must be in [0, 50] and not a calendar year (1950..2100).
    - If scope is provided (candidate LLM extraction), only 'total_career' is accepted.
    - Number must sit next to 'years', 'yrs', or 'decade(s)'.
    - 'ago', 'old', '-old', '-year-old', 'of age' are rejected.
    - 'college', 'university', 'study', 'studies', 'school', 'education', 'degree' are rejected.
    - Zero quotes must match explicit whole-career zero indicators (mode-aware).
    """
    if not quote or not source_text:
        return False
    norm_quote = " ".join(quote.lower().split())
    norm_source = " ".join(source_text.lower().split())
    if norm_quote not in norm_source:
        return False

    if years is not None:
        if years < 0 or years > 50 or (1950 <= years <= 2100):
            return False

    # Scope check: if provided, code accepts only 'total_career'
    if scope is not None and scope != "total_career":
        return False

    # 1. Zero handling (mode-aware)
    if years == 0:
        candidate_zero_patterns = [
            r'\b(?:0|zero)\+?\s*years?(?:\s*of)?\s*(?:work\s*|professional\s*|career\s*)?experience\b',
            r'\bno\s*prior\s*(?:work\s*|professional\s*|career\s*)?experience\b',
            r'\bno\s*(?:professional|work)\s*experience\b',
            r'\bno\s*experience\s*in\s*(?:the\s*)?workforce\b',
        ]
        if mode == "candidate":
            return any(re.search(p, norm_quote) for p in candidate_zero_patterns)
        else:  # JD mode
            jd_zero_patterns = candidate_zero_patterns + [
                r'\b(?:entry[- ]level|no\s*experience\s*required|freshers?(?:\s*welcome)?)\b',
                r'\b0\s*(?:-|to)\s*\d+\s*years?\b',
            ]
            return any(re.search(p, norm_quote) for p in jd_zero_patterns)

    # 2. Elapsed time / age filters (ago, old, of age)
    if re.search(r'\b(?:\d+|' + NUM_PATTERN.replace('(', '(?:') + r')\s*years?\s*(?:ago\b|old\b|-old\b|-year-old\b|of\s+age\b)', norm_quote):
        return False
    if "graduated" in norm_quote and "ago" in norm_quote:
        return False
    if re.search(r'\b(?:of\s+age|-year-old|-old\b|years?\s+old\b)', norm_quote):
        return False

    # 3. Education tenure filters (college, university, study, school, education, degree)
    if re.search(r'\b(?:college|university|school|study|studies|education|degree)\b', norm_quote):
        return False

    # 4. Number sits next to years / yrs / decade / decades
    has_year_proximity = bool(re.search(
        r'\b(?:' + NUM_PATTERN.replace('(', '(?:') + r'|\d+)\+?\s*(?:years?|yrs?|decades?)\b',
        norm_quote
    ))
    has_decade_proximity = bool(re.search(r'\b(?:a|one|two|\d+)\s+decades?\b', norm_quote))
    if not (has_year_proximity or has_decade_proximity):
        return False

    # 5. Check that stated year matches the number in the quote
    if years is not None:
        num_str = str(years)
        words_for_year = [w for w, v in NUMBER_WORDS.items() if v == years]
        has_digit = bool(re.search(r'\b' + re.escape(num_str) + r'\b', norm_quote))
        has_word = any(re.search(r'\b' + re.escape(w) + r'\b', norm_quote) for w in words_for_year)
        if years == 10 and re.search(r'\b(?:a|one)\s+decade\b', norm_quote):
            has_word = True
        elif years == 20 and re.search(r'\b(?:two|2)\s*decades\b', norm_quote):
            has_word = True
        if not (has_digit or has_word):
            return False

    return True

def extract_candidate_experience(resume_text: str) -> ExperienceResult:
    """
    Extract candidate total experience from resume using high-precision rules.
    Statuses: found, explicit_zero, not_found, error.
    Positive patterns run first and always win over zero wording.
    When multiple experience statements appear, the maximum is taken as a lower bound.
    Generic catch-alls like 'N years in/of <noun>' are excluded to avoid misinterpreting
    skill or education tenure (e.g. '5 years in FastAPI', '4 years in college'); such
    cases fall back to LLM extraction.
    """
    if not resume_text:
        return ExperienceResult(status="not_found", years=None, source="regex")

    try:
        # 1. High-precision positive patterns stating total professional, career, or practice experience
        patterns = [
            # "N(+) years(') (of) [total|overall|professional|relevant|work|career|clinical] experience"
            rf'\b{NUM_PATTERN}\+?\s*years?\'?\s*(?:of\s*)?(?:total\s*|overall\s*|professional\s*|relevant\s*|work\s*|career\s*|clinical\s*)?experience\b',
            # "experience of N years"
            rf'\bexperience\s*(?:of\s*)?{NUM_PATTERN}\+?\s*years?\b',
            # "N years in the industry/field/profession/workforce/practice"
            rf'\b{NUM_PATTERN}\+?\s*years?\s*in\s+(?:the\s+)?(?:industry|field|profession|workforce|practice)\b',
            # "N years of practice"
            rf'\b{NUM_PATTERN}\+?\s*years?\s*of\s*practice\b',
            # "N years as a/an <role>" (subject to educational role stoplist)
            rf'\b{NUM_PATTERN}\+?\s*years?\'?\s*(?:(?:of\s*)?(?:total\s*|overall\s*|professional\s*|relevant\s*|work\s*|career\s*)?experience\s+)?as\s+(?:a|an)\s+([a-z]+(?:\s+[a-z]+)?)\b',
            # Decades with experience or industry
            r'\b(?:over\s*a|a|one)\s*decade\s*(?:of\s*)?(?:total\s*|overall\s*|professional\s*|relevant\s*|work\s*|career\s*|clinical)?\s*experience\b',
            r'\btwo\s*decades\s*(?:of\s*)?(?:total\s*|overall\s*|professional\s*|relevant\s*|work\s*|career\s*|clinical)?\s*experience\b',
            r'\b(?:over\s*a|a|one)\s*decade\s*in\s+(?:the\s+)?(?:industry|workforce|field|profession|practice)\b',
            r'\btwo\s*decades\s*in\s+(?:the\s+)?(?:industry|workforce|field|profession|practice)\b',
        ]

        matches = []
        for p in patterns:
            for m in re.finditer(p, resume_text, re.IGNORECASE):
                # Elapsed time / age rejection
                after_text = resume_text[m.end():m.end() + 25].lower()
                if re.match(r'^\s*(?:ago\b|old\b|-old\b|-year-old\b|of\s+age\b)', after_text):
                    continue
                # Education tenure rejection
                if re.match(r'^\s*(?:in|of)\s+(?:college|university|school|study|studies|education|degree)\b', after_text):
                    continue

                before_text = resume_text[max(0, m.start() - 25):m.start()].lower()
                if "graduated" in before_text and "ago" in after_text:
                    continue

                groups = m.groups()
                # Check role stoplist for "N years as a/an <role>"
                if len(groups) >= 2 and groups[1]:
                    role_str = groups[1].lower().strip()
                    first_word = role_str.split()[0]
                    if first_word in ROLE_STOPLIST or role_str in ROLE_STOPLIST:
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
                logger.info(
                    f"Candidate experience matches differ by >2 years: {years_list}, "
                    f"taking max {max_years} as a lower bound for total experience"
                )
            best_match = next(item for item in matches if item[0] == max_years)
            if max_years == 0:
                return ExperienceResult(status="explicit_zero", years=0, source="regex", evidence=best_match[1])
            return ExperienceResult(status="found", years=max_years, source="regex", evidence=best_match[1])

        # 2. Whole-career explicit zero checks (positive matches have already won if present)
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
                "evidence_quote": "string",
                "scope": "string"
            },
            temperature=0.0
        )
        status = raw_response.get("status")
        years = raw_response.get("years")
        quote = raw_response.get("evidence_quote")
        scope = raw_response.get("scope")

        if status == "found":
            if not isinstance(years, int) or years < 0 or years > 50:
                return ExperienceResult(status="not_found", years=None, source="llm")
            if scope != "total_career":
                logger.warning(f"Candidate experience rejected due to scope {scope!r} != 'total_career': quote={quote!r}")
                return ExperienceResult(status="not_found", years=None, source="llm")
            if not verify_evidence_quote(quote, resume_text, years, mode="candidate", scope=scope):
                logger.warning(f"Candidate experience quote verification failed: quote={quote!r}, years={years}")
                return ExperienceResult(status="not_found", years=None, source="llm")
            return ExperienceResult(status="found", years=years, source="llm", evidence=quote)

        elif status == "explicit_zero":
            if scope and scope != "total_career":
                return ExperienceResult(status="not_found", years=None, source="llm")
            if quote and not verify_evidence_quote(quote, resume_text, 0, mode="candidate", scope="total_career"):
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

    ai_client = client or GenAIClient()
    model_name = getattr(ai_client, "model", None) or getattr(settings, "ai_model", "default")
    jd_hash = hashlib.sha256(jd_text.encode('utf-8')).hexdigest()[:16]
    cache_key = f"jd_exp:{EXPERIENCE_EXTRACTION_PROMPT_VERSION}:{model_name}:{jd_hash}"
    cache_manager = CacheManager()

    if getattr(settings, "cache_enabled", True):
        cached = await cache_manager.get(cache_key)
        if cached and isinstance(cached, dict):
            return ExperienceResult(
                status=cached.get("status", "not_specified"),
                years=cached.get("years"),
                source=cached.get("source", "llm"),
                evidence=cached.get("evidence")
            )

    try:
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

        result = None
        if status == "found":
            if not isinstance(years, int) or years < 0 or years > 50:
                result = ExperienceResult(status="not_specified", years=None, source="llm")
            elif not verify_evidence_quote(quote, jd_text, years, mode="jd"):
                logger.warning(f"JD experience quote verification failed: quote={quote!r}, years={years}")
                result = ExperienceResult(status="not_specified", years=None, source="llm")
            else:
                result = ExperienceResult(status="found", years=years, source="llm", evidence=quote)

        elif status == "explicit_zero":
            if quote and not verify_evidence_quote(quote, jd_text, 0, mode="jd"):
                result = ExperienceResult(status="not_specified", years=None, source="llm")
            else:
                result = ExperienceResult(status="explicit_zero", years=0, source="llm", evidence=quote)

        else:
            result = ExperienceResult(status="not_specified", years=None, source="llm")

        if getattr(settings, "cache_enabled", True) and result.status in ("found", "explicit_zero"):
            await cache_manager.set(
                cache_key,
                {"status": result.status, "years": result.years, "source": result.source, "evidence": result.evidence},
                ttl=getattr(settings, "cache_ttl_jd", 604800)
            )
        return result

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


