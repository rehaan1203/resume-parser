"""Unified Date Span & Experience Calculation Engine (D5 Specification).

Implements 7 date span formats, interval union overlap deduplication,
internship credit rules, and stated vs computed experience precedence.
"""
import re
from datetime import date
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any, Union
from dataclasses import dataclass

class SpanType(str, Enum):
    EMPLOYMENT = "employment"
    INTERNSHIP = "internship"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    VOLUNTEER = "volunteer"
    PROJECT = "project"
    OTHER = "other"

@dataclass
class DateSpan:
    raw_text: str
    start_date: date
    end_date: date
    span_type: SpanType = SpanType.EMPLOYMENT

    @property
    def duration_days(self) -> int:
        return max(0, (self.end_date - self.start_date).days)

    @property
    def duration_years(self) -> float:
        return round(self.duration_days / 365.25, 2)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

SEASON_MAP = {
    "spring": (3, 1, 5, 31),
    "summer": (6, 1, 8, 31),
    "fall": (9, 1, 11, 30),
    "autumn": (9, 1, 11, 30),
    "winter": (12, 1, 2, 28),
}

DEFAULT_FROZEN_DATE = date(2026, 10, 28)
_REFERENCE_DATE_OVERRIDE: Optional[date] = None

def get_reference_date() -> date:
    """Return configured frozen reference date (for hermetic tests) or today's date in production."""
    if _REFERENCE_DATE_OVERRIDE is not None:
        return _REFERENCE_DATE_OVERRIDE
    try:
        from app.config import settings
        frozen_str = getattr(settings, "frozen_reference_date", None)
        if frozen_str:
            parts = [int(p) for p in str(frozen_str).split("-")]
            return date(parts[0], parts[1], parts[2])
    except Exception:
        pass
    return date.today()


def format_clean_years(val: float) -> Union[int, float]:
    """Round experience years intelligently to 1 decimal place (keeping whole numbers as int, preserving e.g. 1.3, 1.5, 1.8)."""
    r = round(float(val), 1)
    if abs(r - round(r)) < 0.05:
        return int(round(r))
    return r

def _parse_single_date(text: str, is_end: bool = False, ref_date: Optional[date] = None) -> Optional[date]:
    """Parse a single date component string into a calendar date."""
    if not text:
        return None
    ref = ref_date or get_reference_date()
    t = text.strip().lower()

    if t in ("present", "current", "now", "ongoing", "till date", "to date"):
        return ref

    # 1. Season YYYY (e.g. Summer 2021)
    season_match = re.match(r'^(spring|summer|fall|autumn|winter)\s+(\d{4})$', t)
    if season_match:
        s_name, year_str = season_match.groups()
        y = int(year_str)
        sm, sd, em, ed = SEASON_MAP[s_name]
        if is_end:
            return date(y + (1 if s_name == "winter" else 0), em, ed)
        return date(y, sm, sd)

    # 2. Month'YY (e.g. Jul'19, Jan'20)
    month_apostrophe = re.match(r"^([a-z]+)['’](\d{2})$", t)
    if month_apostrophe:
        m_name, y_short = month_apostrophe.groups()
        if m_name in MONTH_MAP:
            m = MONTH_MAP[m_name]
            y = 2000 + int(y_short)
            if is_end:
                return date(y, m, 28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31))
            return date(y, m, 1)

    # 3. MM/YYYY or MM.YYYY (e.g. 07/2019, 9.2019)
    slash_dot = re.match(r"^(\d{1,2})[/.](\d{4})$", t)
    if slash_dot:
        m = int(slash_dot.group(1))
        y = int(slash_dot.group(2))
        if 1 <= m <= 12 and 1950 <= y <= 2100:
            if is_end:
                return date(y, m, 28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31))
            return date(y, m, 1)

    # 4. Month YYYY (e.g. July 2019, Jan 2021)
    month_year = re.match(r"^([a-z]+)\s+(\d{4})$", t)
    if month_year:
        m_name, y_str = month_year.groups()
        if m_name in MONTH_MAP:
            m = MONTH_MAP[m_name]
            y = int(y_str)
            if is_end:
                return date(y, m, 28 if m == 2 else (30 if m in (4, 6, 9, 11) else 31))
            return date(y, m, 1)

    # 5. YYYY (e.g. 2019)
    year_only = re.match(r"^(\d{4})$", t)
    if year_only:
        y = int(year_only.group(1))
        if 1950 <= y <= 2100:
            if is_end:
                return date(y, 12, 31)
            return date(y, 1, 1)

    return None

def parse_date_span_string(span_str: str, span_type: SpanType = SpanType.EMPLOYMENT) -> Optional[DateSpan]:
    """Parse a date span string like 'Jan 2018 - Mar 2021' or '2019 - Present'."""
    if not span_str:
        return None

    # Academic span: strictly 2019-20 or 2019-2020 at full string
    academic_match = re.match(r'^\s*(20\d{2})\s*[-–—]\s*(\d{2})\s*$', span_str.strip())
    if academic_match:
        y1 = int(academic_match.group(1))
        y2 = int(str(y1)[:2] + academic_match.group(2))
        return DateSpan(raw_text=span_str, start_date=date(y1, 1, 1), end_date=date(y2, 12, 31), span_type=span_type)

    # Split by standard separators: -, –, —, to, until
    parts = re.split(r'\s*(?:[-–—]|to|until)\s*', span_str.strip(), maxsplit=1)
    if len(parts) != 2:
        return None

    start = _parse_single_date(parts[0], is_end=False)
    end = _parse_single_date(parts[1], is_end=True)

    if start and end and start <= end:
        return DateSpan(raw_text=span_str, start_date=start, end_date=end, span_type=span_type)
    return None

def extract_all_date_spans_from_text(text: str) -> List[DateSpan]:
    """Scan resume text and extract all verifiable date spans."""
    if not text:
        return []

    spans: List[DateSpan] = []
    patterns = [
        # Month'YY - Present / Month'YY
        r"\b(?:[a-zA-Z]+['’]\d{2})\s*(?:[-–—]|to)\s*(?:present|current|now|ongoing|till date|[a-zA-Z]+['’]\d{2})\b",
        # Month YYYY - Present / Month YYYY
        r"\b(?:[a-zA-Z]+\s+\d{4})\s*(?:[-–—]|to)\s*(?:present|current|now|ongoing|till date|[a-zA-Z]+\s+\d{4})\b",
        # MM/YYYY - Present / MM/YYYY
        r"\b(?:\d{1,2}[/.]\d{4})\s*(?:[-–—]|to)\s*(?:present|current|now|ongoing|till date|\d{1,2}[/.]\d{4})\b",
        # Season YYYY - Season YYYY / Present
        r"\b(?:(?:Spring|Summer|Fall|Autumn|Winter)\s+\d{4})\s*(?:[-–—]|to)\s*(?:present|current|now|ongoing|till date|(?:Spring|Summer|Fall|Autumn|Winter)\s+\d{4})\b",
        # YYYY - Present / YYYY
        r"\b(?:19\d{2}|20\d{2})\s*(?:[-–—]|to)\s*(?:present|current|now|ongoing|till date|19\d{2}|20\d{2})\b",
        # Academic 2019-20
        r"\b20\d{2}\s*[-–—]\s*\d{2}\b",
    ]

    def _detect_section_above(pos: int) -> Optional[SpanType]:
        """Identify the most recent section heading preceding pos, if any."""
        preceding = text[:pos]
        heading_re = re.compile(
            r'^\s*(?:work\s+experience|professional\s+experience|employment(?:\s+history)?|experience|'
            r'internships?|projects?|personal\s+projects?|academic\s+projects?|'
            r'education|academic\s+background|certifications?|licenses?|volunteer(?:ing)?)\b[:\s]*$',
            re.IGNORECASE | re.MULTILINE,
        )
        last_match = None
        for hm in heading_re.finditer(preceding):
            last_match = hm
        if not last_match:
            return None
        h = last_match.group(0).strip().lower()
        if "intern" in h:
            return SpanType.INTERNSHIP
        if "project" in h:
            return SpanType.PROJECT
        if "education" in h or "academic" in h:
            return SpanType.EDUCATION
        if "certif" in h or "licens" in h:
            return SpanType.CERTIFICATION
        if "volunteer" in h:
            return SpanType.VOLUNTEER
        return SpanType.EMPLOYMENT

    claimed_ranges: List[Tuple[int, int]] = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            # Prevent coarse YYYY patterns from re-matching tail substrings inside already-matched Month YYYY spans
            if any(s <= m.start() and m.end() <= e for s, e in claimed_ranges):
                continue

            raw_match = m.group(0)
            # Restrict local line context (current line + 1 line above; never bleed into next blank-line block below)
            above_block = text[max(0, m.start() - 80):m.start()].split("\n\n")[-1]
            same_line_end = text.find("\n", m.end())
            below_line = text[m.end(): same_line_end if same_line_end != -1 else min(len(text), m.end() + 40)]
            local_context = f"{above_block} {raw_match} {below_line}".lower()

            section_type = _detect_section_above(m.start())
            if re.search(r'\b(?:intern|internship|co-op|summer trainee)\b', local_context):
                span_type = SpanType.INTERNSHIP
            elif section_type in (SpanType.PROJECT, SpanType.EDUCATION, SpanType.CERTIFICATION, SpanType.VOLUNTEER):
                span_type = section_type
            elif re.search(r'\b(?:capstone project|academic project|hackathon)\b', local_context):
                span_type = SpanType.PROJECT
            elif re.search(r'\b(?:university|college|school|bachelor|master|degree|gpa|phd|diploma|bsn|msn|b\.?tech|m\.?tech|b\.?e\.?|institute of technology|high school|cbse|icse|education)\b', local_context):
                span_type = SpanType.EDUCATION
            elif re.search(r'\b(?:certified|certification|licensure|license|exam)\b', local_context):
                span_type = SpanType.CERTIFICATION
            elif re.search(r'\b(?:volunteer|nonprofit|pro bono)\b', local_context):
                span_type = SpanType.VOLUNTEER
            else:
                span_type = SpanType.EMPLOYMENT

            parsed = parse_date_span_string(raw_match, span_type=span_type)
            if parsed and parsed not in spans:
                claimed_ranges.append((m.start(), m.end()))
                spans.append(parsed)

    return spans

def calculate_interval_union(intervals: List[Tuple[date, date]]) -> float:
    """
    Calculate the mathematical union of continuous date intervals.
    Overlapping periods are merged so concurrent roles are credited once.
    """
    if not intervals:
        return 0.0

    valid_intervals = [i for i in intervals if i[0] <= i[1]]
    if not valid_intervals:
        return 0.0

    valid_intervals.sort(key=lambda x: x[0])

    merged: List[List[date]] = []
    for start, end in valid_intervals:
        if not merged:
            merged.append([start, end])
        else:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1][1] = max(prev_end, end)
            else:
                merged.append([start, end])

    total_days = sum((m[1] - m[0]).days for m in merged)
    return round(total_days / 365.25, 2)

def compute_effective_experience(
    spans: List[DateSpan],
    stated_years: Optional[float] = None,
    user_entered_years: Optional[float] = None
) -> Dict[str, Any]:
    """
    Apply D5 Precedence & Internship Credit Rules.
    - If user entered override exists, it wins.
    - Internships credited at 50% if professional experience < 2.0 yrs, else 0%.
    - Effective = max(stated, computed).
    - Flag discrepancy if |stated - computed| > 2.0 years.
    """
    emp_intervals = [(s.start_date, s.end_date) for s in spans if s.span_type == SpanType.EMPLOYMENT]
    intern_intervals = [(s.start_date, s.end_date) for s in spans if s.span_type == SpanType.INTERNSHIP]

    t_employment = calculate_interval_union(emp_intervals)
    t_internship = calculate_interval_union(intern_intervals)

    if t_employment < 2.0:
        credited_internship = round(t_internship * 0.5, 2)
    else:
        credited_internship = 0.0

    t_computed = round(t_employment + credited_internship, 2)

    if user_entered_years is not None and user_entered_years >= 0:
        clean_user = format_clean_years(user_entered_years)
        return {
            "effective_years": clean_user,
            "effective_years_exact": round(float(user_entered_years), 2),
            "source": "user_override",
            "t_stated": stated_years,
            "t_computed": t_computed,
            "t_employment": t_employment,
            "credited_internship": credited_internship,
            "discrepancy_warning": False,
            "evidence": f"User-entered override: {clean_user} years",
            "spans_count": len(spans)
        }

    discrepancy_warning = False
    discrepancy_note = None

    if stated_years is not None and t_computed > 0:
        if abs(stated_years - t_computed) > 2.0:
            discrepancy_warning = True
            discrepancy_note = f"Candidate claims {stated_years} years, but date intervals sum to {t_computed} years."
        final_years = max(stated_years, t_computed)
        source = "stated_max" if final_years == stated_years else "computed_dates"
    elif stated_years is not None:
        final_years = stated_years
        source = "stated"
    elif t_computed > 0:
        final_years = t_computed
        source = "computed_dates"
    else:
        final_years = 0.0
        source = "none"

    clean_effective = format_clean_years(final_years)
    return {
        "effective_years": clean_effective,
        "effective_years_exact": round(final_years, 2),
        "source": source,
        "t_stated": stated_years,
        "t_computed": t_computed,
        "t_employment": t_employment,
        "credited_internship": credited_internship,
        "discrepancy_warning": discrepancy_warning,
        "discrepancy_note": discrepancy_note,
        "evidence": f"Effective experience derived via {source}: {clean_effective} years",
        "spans_count": len(spans)
    }
