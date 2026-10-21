"""Prompts and builder functions for seniority alignment analysis."""

SENIORITY_ALIGNMENT_PROMPT_VERSION = "v1"


def build_seniority_alignment_prompt(
    years_experience: int,
    required_years: int,
    your_level: str,
    required_level: str,
    gap: int,
    alignment_status: str
) -> str:
    """Build prompt for generating seniority alignment summary, recommendations, and next steps."""
    return f"""
        You are a seniority alignment analyzer.
        
        INPUT DATA:
        - Your Experience: {years_experience} years
        - Required Experience: {required_years} years
        - Your Level: {your_level}
        - Required Level: {required_level}
        - Experience Gap: {gap} years
        - Alignment Status: {alignment_status}
        
        TASK:
        Generate a comprehensive seniority alignment section with:
        
        1. SUMMARY: A single, punchy sentence (max 15 words) explaining the gap and what it means for the candidate.
        2. RECOMMENDATION: Specific advice on what level roles to target and how to bridge the gap.
        3. NEXT STEPS: 3-5 actionable steps to bridge the gap.
        
        Return exactly this JSON schema:
        {{
          "summary": "string",
          "recommendation": "string",
          "next_steps": ["string"]
        }}
        """
