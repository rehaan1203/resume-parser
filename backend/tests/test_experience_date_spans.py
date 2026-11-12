"""Hermetic unit tests for D5 Unified Experience & Date Span Engine."""
import pytest
from datetime import date
from app.utils.date_span_calculator import (
    DateSpan,
    SpanType,
    parse_date_span_string,
    extract_all_date_spans_from_text,
    calculate_interval_union,
    compute_effective_experience,
    get_reference_date
)
from app.utils.seniority_calculator import calculate_seniority_score_and_gap
from app.config import settings


@pytest.fixture(autouse=True)
def pin_frozen_reference_date(monkeypatch):
    """Pin reference date in hermetic unit tests so time-dependent spans stay deterministic."""
    monkeypatch.setattr("app.utils.date_span_calculator._REFERENCE_DATE_OVERRIDE", date(2026, 10, 28))

def test_parse_jul_apostrophe_year():
    span = parse_date_span_string("Jul'19 - Present")
    assert span is not None
    assert span.start_date == date(2019, 7, 1)
    assert span.end_date == get_reference_date()

def test_parse_slash_and_dot_dates():
    span1 = parse_date_span_string("07/2019 - 03/2021")
    assert span1 is not None
    assert span1.start_date == date(2019, 7, 1)
    assert span1.end_date == date(2021, 3, 31)

    span2 = parse_date_span_string("09.2019 - 12.2022")
    assert span2 is not None
    assert span2.start_date == date(2019, 9, 1)
    assert span2.end_date == date(2022, 12, 31)

def test_parse_academic_span_year():
    span = parse_date_span_string("2019-20")
    assert span is not None
    assert span.start_date == date(2019, 1, 1)
    assert span.end_date == date(2020, 12, 31)

def test_parse_season_summer():
    span = parse_date_span_string("Summer 2021 - Fall 2022")
    assert span is not None
    assert span.start_date == date(2021, 6, 1)
    assert span.end_date == date(2022, 11, 30)

def test_present_till_date_frozen():
    span = parse_date_span_string("Jan 2020 - Till date")
    assert span is not None
    assert span.start_date == date(2020, 1, 1)
    assert span.end_date == date(2026, 10, 28)

def test_overlapping_roles_deduplicated():
    # Role A: Jan 2020 to Dec 2021 (2 years)
    # Role B: Jun 2020 to Jun 2022 (overlap from Jun 2020 to Dec 2021)
    intervals = [
        (date(2020, 1, 1), date(2021, 12, 31)),
        (date(2020, 6, 1), date(2022, 6, 30))
    ]
    total_union = calculate_interval_union(intervals)
    # From Jan 1 2020 to Jun 30 2022 is 2.5 years (911 days / 365.25 = 2.49)
    assert 2.45 <= total_union <= 2.55

def test_internship_discount_entry_vs_senior():
    # 1. Entry candidate (< 2 yrs employment): gets 50% internship credit
    spans_entry = [
        DateSpan("Jan 2023 - Dec 2023", date(2023, 1, 1), date(2023, 12, 31), SpanType.EMPLOYMENT),
        DateSpan("Jun 2022 - Aug 2022", date(2022, 6, 1), date(2022, 8, 31), SpanType.INTERNSHIP),
    ]
    res_entry = compute_effective_experience(spans_entry)
    assert res_entry["t_employment"] < 2.0
    assert res_entry["credited_internship"] > 0

    # 2. Senior candidate (>= 2 yrs employment): gets 0% internship credit
    spans_senior = [
        DateSpan("Jan 2020 - Dec 2023", date(2020, 1, 1), date(2023, 12, 31), SpanType.EMPLOYMENT),
        DateSpan("Jun 2019 - Aug 2019", date(2019, 6, 1), date(2019, 8, 31), SpanType.INTERNSHIP),
    ]
    res_senior = compute_effective_experience(spans_senior)
    assert res_senior["t_employment"] >= 3.9
    assert res_senior["credited_internship"] == 0.0

def test_stated_vs_computed_precedence_and_discrepancy():
    spans = [
        DateSpan("Jan 2021 - Dec 2023", date(2021, 1, 1), date(2023, 12, 31), SpanType.EMPLOYMENT),
    ] # ~3 years
    # Candidate claims 8 years (discrepancy > 2.0)
    res = compute_effective_experience(spans, stated_years=8.0)
    assert res["effective_years"] == 8
    assert res["discrepancy_warning"] is True
    assert "Candidate claims 8.0 years" in res["discrepancy_note"]

def test_user_entered_override():
    spans = [
        DateSpan("Jan 2021 - Dec 2023", date(2021, 1, 1), date(2023, 12, 31), SpanType.EMPLOYMENT),
    ]
    res = compute_effective_experience(spans, stated_years=3.0, user_entered_years=7.0)
    assert res["effective_years"] == 7
    assert res["source"] == "user_override"

def test_extract_all_date_spans_from_text():
    resume = """
    EXPERIENCE
    Senior Clinical Nurse | Mercy Hospital
    Jan 2018 - Mar 2021
    Provided critical care in ICU telemetry ward.

    Staff Nurse | General Hospital
    Apr 2021 - Present
    Assisted in surgical ward.

    EDUCATION
    BSN in Nursing
    2014 - 2018
    """
    spans = extract_all_date_spans_from_text(resume)
    assert len(spans) >= 2
    # Verify employment vs education classification
    types = [s.span_type for s in spans]
    assert SpanType.EMPLOYMENT in types
    assert SpanType.EDUCATION in types


def test_overlapping_month_year_not_duplicated_and_projects_excluded():
    """Ensure 'Aug 2025 – Present' is never double-counted as '2025 – Present' and Projects are excluded from Employment."""
    resume = """
    EXPERIENCE
    Software Engineer | Tech Corp
    Aug 2025 – Present
    Built FastAPI backend services.

    PROJECTS
    RAG Chatbot Capstone Project
    Jan 2024 – May 2024

    EDUCATION
    B.Tech Computer Science | Institute of Technology
    2021 – 2025
    """
    spans = extract_all_date_spans_from_text(resume)
    emp_spans = [s for s in spans if s.span_type == SpanType.EMPLOYMENT]
    proj_spans = [s for s in spans if s.span_type == SpanType.PROJECT]
    edu_spans = [s for s in spans if s.span_type == SpanType.EDUCATION]

    assert len(emp_spans) == 1
    assert emp_spans[0].start_date == date(2025, 8, 1)
    assert len(proj_spans) == 1
    assert len(edu_spans) == 1

    eff = compute_effective_experience(spans)
    assert eff["effective_years"] == 1.2
    assert eff["t_employment"] == 1.24


def test_fractional_years_preserved_intelligently():
    """Verify fractional experience (1.5 yrs, 1.8 yrs) stays exact instead of rounding up/down to whole integers."""
    spans_1_5 = [DateSpan("Jan 2025 - Jun 2026", date(2025, 1, 1), date(2026, 6, 30), SpanType.EMPLOYMENT)]
    res_1_5 = compute_effective_experience(spans_1_5)
    assert res_1_5["effective_years"] == 1.5

    spans_1_8 = [DateSpan("Jan 2025 - Oct 2026", date(2025, 1, 1), date(2026, 10, 28), SpanType.EMPLOYMENT)]
    res_1_8 = compute_effective_experience(spans_1_8)
    assert res_1_8["effective_years"] == 1.8

    sen = calculate_seniority_score_and_gap(1.5, 3)
    assert sen["years_experience"] == 1.5
    assert sen["your_level"] == "Entry"
    assert sen["gap"] == 1.5
    assert sen["seniority_score"] == 70

