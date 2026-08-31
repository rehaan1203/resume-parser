"""Token counting and text truncation utilities."""
import math
from typing import List

def estimate_tokens(text: str) -> int:
    """
    Rough estimate: 1 token ≈ 4 characters for English text.
    More accurate for Gemini models.
    """
    if not text:
        return 0
    # Average tokens per character for English is ~0.25
    return len(text) // 4

def truncate_to_token_limit(text: str, max_tokens: int = 8000) -> str:
    """Truncate text to fit within token limit at sentence boundaries."""
    if estimate_tokens(text) <= max_tokens:
        return text
    
    # Split into sentences
    sentences = text.split('. ')
    truncated = ""
    
    for sent in sentences:
        if estimate_tokens(truncated + sent + ". ") > max_tokens:
            break
        truncated += sent + ". "
    
    return truncated.strip()

def calculate_cost(tokens: int, model: str = "gemini-2.5-flash") -> float:
    """Calculate approximate cost based on token usage."""
    # Pricing (approximate per 1M tokens)
    pricing = {
        "gemini-2.5-flash": 0.30,  # Input
        "text-embedding-004": 0.10  # Input
    }
    cost_per_1m = pricing.get(model, 0.50)
    return (tokens / 1_000_000) * cost_per_1m
