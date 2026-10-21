"""Comprehensive render comparison tests asserting 100% byte-for-byte parity against fixtures."""
from pathlib import Path

from app.prompts.base_prompt import SYSTEM_PROMPT
from app.prompts.analysis_prompt import (
    build_executive_summary_prompt,
    build_mismatch_prompt,
    FRICTION_ANALYSIS_PROMPT,
    SAMPLE_ANALYSIS_PROMPT,
)
from app.prompts.roadmap_prompt import (
    build_upskill_roadmap_prompt,
    build_transition_roadmap_prompt,
    THIRTY_DAY_ROADMAP_PROMPT,
)
from app.prompts.ats_prompt import (
    build_standard_ats_prompt,
    build_transition_ats_prompt,
    build_transition_tips_prompt,
    ATS_OPTIMIZATION_PROMPT,
)
from app.prompts.seniority_prompt import build_seniority_alignment_prompt
from app.prompts.extraction_prompt import (
    build_experience_extraction_prompt,
)
from app.prompts.career_prompt import (
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



# 7. Career Prompts
def test_interview_questions_render():
    assert INTERVIEW_QUESTIONS_PROMPT == read_fixture("interview_questions.txt")


def test_career_advice_render():
    assert CAREER_ADVICE_PROMPT == read_fixture("career_advice.txt")


# 8. Slicing & Truncation Boundary Tests
def test_executive_summary_slicing_behavior():
    """Verify that >3 strengths and >3 gaps are strictly sliced to exactly 3 items."""
    long_strengths = ["S1", "S2", "S3", "S4", "S5"]
    long_gaps = ["G1", "G2", "G3", "G4", "G5"]
    rendered = build_executive_summary_prompt(
        score=85,
        strengths=long_strengths,
        gaps=long_gaps,
        seniority_gap=1
    )
    expected = build_executive_summary_prompt(
        score=85,
        strengths=["S1", "S2", "S3"],
        gaps=["G1", "G2", "G3"],
        seniority_gap=1
    )
    assert rendered == expected
    assert "S1, S2, S3" in rendered
    assert "S4" not in rendered
    assert "G1, G2, G3" in rendered
    assert "G4" not in rendered


def test_transition_roadmap_truncation_behavior():
    """Verify that resume and JD exceeding 2000 characters are strictly truncated at 2000 chars."""
    long_resume = "R" * 3500
    long_jd = "J" * 3500
    rendered = build_transition_roadmap_prompt(
        resume_domain="legal",
        jd_domain="tech",
        resume=long_resume,
        jd=long_jd
    )
    expected = build_transition_roadmap_prompt(
        resume_domain="legal",
        jd_domain="tech",
        resume="R" * 2000,
        jd="J" * 2000
    )
    assert rendered == expected
    assert f"## Resume: {'R' * 2000}\n" in rendered
    assert f"## Job Description: {'J' * 2000}\n" in rendered


def test_transition_tips_truncation_behavior():
    """Verify that transition tips builder strictly truncates resume and JD at 2000 chars."""
    long_resume = "X" * 2500
    long_jd = "Y" * 2500
    rendered = build_transition_tips_prompt(
        resume_domain="legal",
        jd_domain="tech",
        resume=long_resume,
        jd=long_jd
    )
    expected = build_transition_tips_prompt(
        resume_domain="legal",
        jd_domain="tech",
        resume="X" * 2000,
        jd="Y" * 2000
    )
    assert rendered == expected
    assert f"## Resume: {'X' * 2000}\n" in rendered
    assert f"## Job Description: {'Y' * 2000}\n" in rendered

