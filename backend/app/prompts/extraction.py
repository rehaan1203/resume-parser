"""Prompts and builder functions for candidate experience and domain extraction fallbacks."""

EXPERIENCE_EXTRACTION_PROMPT_VERSION = "v1"
DOMAIN_DETECTION_PROMPT_VERSION = "v1"


def build_experience_extraction_prompt(text: str) -> str:
    """Build prompt for LLM fallback extraction of total years of experience."""
    return f"""
        Extract the total years of professional experience from this text.
        Return ONLY a JSON object with a single key 'years' mapping to an integer.
        If no experience is mentioned, return 0.
        
        Text:
        {text[:3000]}
        """


DOMAIN_DETECTION_PROMPT = """
You are a career and domain expert. Analyze the following text (from a resume or job description) and detect its primary professional domain.

Text:
{text}

## Supported Domains:
- legal
- healthcare
- finance
- architecture
- education
- ai_ml
- software
- design
- marketing
- sales
- hr
- operations
- engineering
- science
- unknown

Return ONLY this JSON:
{{
    "domain": "string (must be one of the supported domains)",
    "confidence": "integer (0-100)",
    "evidence": ["list of string keywords found in text"],
    "reasoning": "brief explanation of why this domain was selected"
}}
"""
