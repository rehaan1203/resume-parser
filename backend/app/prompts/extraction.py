"""Prompts and builder functions for candidate experience extraction fallbacks."""

EXPERIENCE_EXTRACTION_PROMPT_VERSION = "v1"


def build_experience_extraction_prompt(text: str) -> str:
    """Build prompt for LLM fallback extraction of total years of experience."""
    return f"""
        Extract the total years of professional experience from this text.
        Return ONLY a JSON object with a single key 'years' mapping to an integer.
        If no experience is mentioned, return 0.
        
        Text:
        {text[:3000]}
        """

