"""Prompts for interview question generation and career guidance."""

INTERVIEW_QUESTIONS_PROMPT_VERSION = "v1"
CAREER_ADVICE_PROMPT_VERSION = "v1"

INTERVIEW_QUESTIONS_PROMPT = """
Generate {num_questions} interview questions based on this resume and job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

SKILL GAPS:
{skill_gaps}

Generate a mix of technical, behavioral, and situational questions.
Focus on areas where the candidate might have gaps or strengths.

Return JSON with questions array containing category, question, expected_answer, hint, and difficulty.
"""

CAREER_ADVICE_PROMPT = """
Provide long-term career guidance based on this resume.

RESUME:
{resume}

EXPERIENCE:
{experience}

CAREER GOALS:
{goals}

Provide short-term and long-term goals, skills to develop, career paths, and salary expectations.
Return JSON with advice object containing all recommendations.
"""

CAREER_ADVICE_RAG_PROMPT = """
Provide long-term career guidance based on this resume.

RESUME:
{resume}

EXPERIENCE:
{experience}

CAREER GOALS:
{goals}

SKILL GAPS:
{skill_gaps}

VERIFIED ACCREDITED RESOURCES:
{verified_resources}

Provide short-term and long-term goals, skills to develop, career paths, and salary expectations.
Ground recommendations strictly in the verified resources provided above. Do not invent external links.
Return JSON with advice object containing all recommendations.
"""
