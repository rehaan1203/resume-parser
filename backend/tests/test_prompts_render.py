"""Comprehensive render comparison tests asserting 100% byte-for-byte parity against fixtures."""
from pathlib import Path

from app.prompts.base import SYSTEM_PROMPT
from app.prompts.analysis import (
    build_executive_summary_prompt,
    build_mismatch_prompt,
    FRICTION_ANALYSIS_PROMPT,
    SAMPLE_ANALYSIS_PROMPT,
)
from app.prompts.roadmap import (
    build_upskill_roadmap_prompt,
    build_transition_roadmap_prompt,
    THIRTY_DAY_ROADMAP_PROMPT,
)
from app.prompts.ats import (
    build_standard_ats_prompt,
    build_transition_ats_prompt,
    build_transition_tips_prompt,
    ATS_OPTIMIZATION_PROMPT,
)
from app.prompts.seniority import build_seniority_alignment_prompt
from app.prompts.extraction import (
    build_experience_extraction_prompt,
    DOMAIN_DETECTION_PROMPT,
)
from app.prompts.career import (
    INTERVIEW_QUESTIONS_PROMPT,
    CAREER_ADVICE_PROMPT,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prompts"


def read_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# 1. Base Prompts
def test_system_prompt_render():
    assert SYSTEM_PROMPT == read_fixture("system_prompt.txt")


# 2. Analysis Prompts & Builders
def test_executive_summary_prompt_render():
    rendered = build_executive_summary_prompt(
        score=75,
        strengths=["Python", "FastAPI", "PostgreSQL"],
        gaps=["Docker", "Kubernetes", "AWS"],
        seniority_gap=2
    )
    assert rendered == read_fixture("executive_summary.txt")


def test_domain_mismatch_prompt_render():
    rendered = build_mismatch_prompt(
        resume_domain="Lawyer/Legal Professional",
        jd_domain="Software Engineer"
    )
    assert rendered == read_fixture("domain_mismatch.txt")


def test_friction_analysis_prompt_render():
    assert FRICTION_ANALYSIS_PROMPT == read_fixture("friction_analysis.txt")


def test_sample_analysis_prompt_render():
    assert SAMPLE_ANALYSIS_PROMPT == read_fixture("sample_analysis.txt")


# 3. Roadmap Builders & Static
def test_roadmap_mini_render():
    rendered = build_upskill_roadmap_prompt(
        gaps=["Docker", "Kubernetes", "AWS"],
        gap_type="mini_upskill"
    )
    assert rendered == read_fixture("roadmap_mini.txt")


def test_roadmap_short_render():
    rendered = build_upskill_roadmap_prompt(
        gaps=["Docker", "Kubernetes", "AWS"],
        gap_type="short_upskill"
    )
    assert rendered == read_fixture("roadmap_short.txt")


def test_roadmap_standard_render():
    rendered = build_upskill_roadmap_prompt(
        gaps=["Docker", "Kubernetes", "AWS"],
        gap_type="standard_upskill"
    )
    assert rendered == read_fixture("roadmap_standard.txt")


def test_roadmap_extended_render():
    rendered = build_upskill_roadmap_prompt(
        gaps=["Docker", "Kubernetes", "AWS"],
        gap_type="extended_upskill"
    )
    assert rendered == read_fixture("roadmap_extended.txt")


def test_roadmap_career_change_render():
    rendered = build_upskill_roadmap_prompt(
        gaps=["Docker", "Kubernetes", "AWS"],
        gap_type="career_change"
    )
    assert rendered == read_fixture("roadmap_career_change.txt")


def test_transition_roadmap_render():
    rendered = build_transition_roadmap_prompt(
        resume_domain="Lawyer/Legal Professional",
        jd_domain="Software Engineer",
        resume="Sample resume text for candidate with 5 years experience...",
        jd="Sample job description text for Senior Engineer..."
    )
    assert rendered == read_fixture("transition_roadmap.txt")


def test_thirty_day_roadmap_render():
    assert THIRTY_DAY_ROADMAP_PROMPT == read_fixture("thirty_day_roadmap.txt")


# 4. ATS Prompts & Builders
def test_standard_ats_prompt_render():
    rendered = build_standard_ats_prompt(
        gaps=["Docker", "Kubernetes", "AWS"]
    )
    assert rendered == read_fixture("ats_standard.txt")


def test_transition_ats_prompt_render():
    rendered = build_transition_ats_prompt(
        resume_domain="Lawyer/Legal Professional",
        jd_domain="Software Engineer",
        gaps=["Docker", "Kubernetes", "AWS"]
    )
    assert rendered == read_fixture("ats_mismatch.txt")


def test_transition_tips_prompt_render():
    rendered = build_transition_tips_prompt(
        resume_domain="Lawyer/Legal Professional",
        jd_domain="Software Engineer",
        resume="Sample resume text for candidate with 5 years experience...",
        jd="Sample job description text for Senior Engineer..."
    )
    assert rendered == read_fixture("transition_tips.txt")


def test_ats_optimization_prompt_render():
    assert ATS_OPTIMIZATION_PROMPT == read_fixture("ats_optimization.txt")


# 5. Seniority Alignment Variants
def test_seniority_match_render():
    rendered = build_seniority_alignment_prompt(
        years_experience=5,
        required_years=5,
        your_level="Senior",
        required_level="Senior",
        gap=0,
        alignment_status="match"
    )
    assert rendered == read_fixture("seniority_match.txt")


def test_seniority_minor_gap_render():
    rendered = build_seniority_alignment_prompt(
        years_experience=3,
        required_years=5,
        your_level="Mid",
        required_level="Senior",
        gap=2,
        alignment_status="minor_gap"
    )
    assert rendered == read_fixture("seniority_minor_gap.txt")


def test_seniority_large_gap_render():
    rendered = build_seniority_alignment_prompt(
        years_experience=1,
        required_years=6,
        your_level="Entry",
        required_level="Senior",
        gap=5,
        alignment_status="significant_gap"
    )
    assert rendered == read_fixture("seniority_large_gap.txt")


# 6. Extraction Prompts
def test_experience_extraction_render():
    sample_text = "Lead software developer managing distributed systems and enterprise infrastructure."
    rendered = build_experience_extraction_prompt(sample_text)
    assert rendered == read_fixture("experience_extraction.txt")


def test_domain_detection_render():
    assert DOMAIN_DETECTION_PROMPT == read_fixture("domain_detection.txt")


# 7. Career Prompts
def test_interview_questions_render():
    assert INTERVIEW_QUESTIONS_PROMPT == read_fixture("interview_questions.txt")


def test_career_advice_render():
    assert CAREER_ADVICE_PROMPT == read_fixture("career_advice.txt")
