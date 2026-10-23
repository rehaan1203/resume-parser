"""Hermetic table tests for extract_candidate_experience and extract_required_experience."""
import pytest
from app.utils.experience_extractor import (
    extract_candidate_experience,
    extract_required_experience,
    ExperienceResult
)

# Table of test cases: (kind, text, expected_status, expected_years)
RESUME_TEST_CASES = [
    ("EXPERIENCE\n2019 - Present Acme Corp", "not_found", None),
    ("Experience: 2018 - 2023", "not_found", None),
    ("5+ years' experience", "found", 5),
    ("10 yrs", "not_found", None),
    ("ten years", "not_found", None),
    ("ten years of experience", "found", 10),
    ("10+ years in nursing", "found", 10),
    ("over a decade of experience", "found", 10),
    ("graduated 5 years ago", "not_found", None),
    ("5 years old", "not_found", None),
    ("seeking entry-level roles", "not_found", None),
    ("recent graduate with two internships", "not_found", None),
    ("Led a team for 2 years", "not_found", None),
    ("Python for 3 years, Docker for 2 years", "not_found", None),
    ("0 years of experience", "explicit_zero", 0),
    ("no prior work experience", "explicit_zero", 0),
    ("no experience", "explicit_zero", 0),
    ("Senior developer with 8 years of professional experience", "found", 8),
    ("Nurse with 5 years in intensive care", "found", 5),
    ("two decades of experience in law", "found", 20),
]

JD_TEST_CASES = [
    ("3+ years required, 7 preferred", "found", 3),
    ("0-2 years", "explicit_zero", 0),
    ("entry-level, no experience required", "explicit_zero", 0),
    ("freshers welcome", "explicit_zero", 0),
    ("minimum of 4 years experience required", "found", 4),
    ("at least 5 years of software engineering", "found", 5),
    ("3-5 years experience", "found", 3),
    ("3 to 5 years experience", "found", 3),
    ("5+ years", "found", 5),
    ("7 yrs exp", "found", 7),
    ("Software Engineer position. Competitive benefits and culture.", "not_specified", None),
]

@pytest.mark.parametrize("text,expected_status,expected_years", RESUME_TEST_CASES)
def test_candidate_experience_extraction_table(text, expected_status, expected_years):
    result = extract_candidate_experience(text)
    assert isinstance(result, ExperienceResult)
    assert result.status == expected_status
    assert result.years == expected_years

@pytest.mark.parametrize("text,expected_status,expected_years", JD_TEST_CASES)
def test_required_experience_extraction_table(text, expected_status, expected_years):
    result = extract_required_experience(text)
    assert isinstance(result, ExperienceResult)
    assert result.status == expected_status
    assert result.years == expected_years
