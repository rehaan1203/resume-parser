"""Harness test asserting that production callers generate prompts identical to fixtures.

This test executes the real caller methods in explainer.py, transition.py, and experience_extractor.py,
intercepts the prompt passed to the LLM client, and asserts that it matches the fixture file.
It passes against the current inline code and MUST continue passing after callers are migrated in Phase 4.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.ai.explainer import Phase3Explainer
from app.api.routes.transition import generate_transition_roadmap, generate_transition_tips
from app.utils.experience_extractor import extract_years_experience

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prompts"

# Fixed test inputs used across all fixtures
SCORE = 75
STRENGTHS = ["Python", "FastAPI", "PostgreSQL"]
GAPS = ["Docker", "Kubernetes", "AWS"]
SENIORITY_GAP = 2
RESUME_DOMAIN = "Lawyer/Legal Professional"
JD_DOMAIN = "Software Engineer"
RESUME_TEXT = "Sample resume text for candidate with 5 years experience..."
JD_TEXT = "Sample job description text for Senior Engineer..."


def read_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.mark.asyncio
async def test_caller_executive_summary():
    explainer = Phase3Explainer()
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    explainer.client.generate_structured_content = mock_generate
    await explainer.generate_executive_summary(
        score=SCORE,
        strengths=STRENGTHS,
        gaps=GAPS,
        seniority_gap=SENIORITY_GAP
    )
    assert captured_prompt == read_fixture("executive_summary.txt")


@pytest.mark.asyncio
async def test_caller_mismatch_message():
    explainer = Phase3Explainer()
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    explainer.client.generate_structured_content = mock_generate
    await explainer.generate_mismatch_message(
        resume_domain=RESUME_DOMAIN,
        jd_domain=JD_DOMAIN
    )
    assert captured_prompt == read_fixture("domain_mismatch.txt")


@pytest.mark.asyncio
async def test_caller_ats_standard():
    explainer = Phase3Explainer()
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    explainer.client.generate_structured_content = mock_generate
    await explainer.generate_ats_optimization(
        gaps=GAPS,
        jd_text=JD_TEXT,
        domain_analysis={"is_mismatch": False}
    )
    assert captured_prompt == read_fixture("ats_standard.txt")


@pytest.mark.asyncio
async def test_caller_ats_mismatch():
    explainer = Phase3Explainer()
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    explainer.client.generate_structured_content = mock_generate
    await explainer.generate_ats_optimization(
        gaps=GAPS,
        jd_text=JD_TEXT,
        domain_analysis={"is_mismatch": True, "resume_domain": RESUME_DOMAIN, "jd_domain": JD_DOMAIN}
    )
    assert captured_prompt == read_fixture("ats_mismatch.txt")


@pytest.mark.asyncio
@pytest.mark.parametrize("gap_type,fixture_file", [
    ("mini_upskill", "roadmap_mini.txt"),
    ("short_upskill", "roadmap_short.txt"),
    ("standard_upskill", "roadmap_standard.txt"),
    ("extended_upskill", "roadmap_extended.txt"),
    ("career_change", "roadmap_career_change.txt"),
])
async def test_caller_roadmap_variants(gap_type, fixture_file):
    explainer = Phase3Explainer()
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    explainer.client.generate_structured_content = mock_generate
    await explainer.generate_roadmap(gaps=GAPS, gap_type=gap_type)
    assert captured_prompt == read_fixture(fixture_file)


@pytest.mark.asyncio
@pytest.mark.parametrize("years,req_years,your_level,req_level,gap,fixture_file", [
    (5, 5, "Senior", "Senior", 0, "seniority_match.txt"),
    (3, 5, "Mid", "Senior", 2, "seniority_minor_gap.txt"),
    (1, 6, "Entry", "Senior", 5, "seniority_large_gap.txt"),
])
async def test_caller_seniority_alignment_variants(years, req_years, your_level, req_level, gap, fixture_file):
    explainer = Phase3Explainer()
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    explainer.client.generate_structured_content = mock_generate
    await explainer.generate_seniority_alignment(
        years_experience=years,
        required_years=req_years,
        your_level=your_level,
        required_level=req_level,
        gap=gap,
        domain_analysis={"is_mismatch": False}
    )
    assert captured_prompt == read_fixture(fixture_file)


@pytest.mark.asyncio
async def test_caller_transition_roadmap():
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    with patch("app.api.routes.transition.GenAIClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.generate_structured_content = mock_generate
        mock_client_cls.return_value = mock_instance

        await generate_transition_roadmap(
            resume_domain=RESUME_DOMAIN,
            jd_domain=JD_DOMAIN,
            resume=RESUME_TEXT,
            jd=JD_TEXT
        )
    assert captured_prompt == read_fixture("transition_roadmap.txt")


@pytest.mark.asyncio
async def test_caller_transition_tips():
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    with patch("app.api.routes.transition.GenAIClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.generate_structured_content = mock_generate
        mock_client_cls.return_value = mock_instance

        await generate_transition_tips(
            resume_domain=RESUME_DOMAIN,
            jd_domain=JD_DOMAIN,
            resume=RESUME_TEXT,
            jd=JD_TEXT
        )
    assert captured_prompt == read_fixture("transition_tips.txt")


@pytest.mark.asyncio
async def test_caller_experience_extraction():
    captured_prompt = None

    async def mock_generate(prompt, output_schema, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {}

    sample_text = "Lead software developer managing distributed systems and enterprise infrastructure."
    with patch("app.utils.experience_extractor.GenAIClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.generate_structured_content = mock_generate
        mock_client_cls.return_value = mock_instance

        with patch("app.utils.experience_extractor.CacheManager") as mock_cache_cls:
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None
            mock_cache_cls.return_value = mock_cache
            await extract_years_experience(sample_text)

    assert captured_prompt == read_fixture("experience_extraction.txt")
