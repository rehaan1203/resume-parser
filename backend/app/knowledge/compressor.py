"""Contextual Fluff Compressor & Syllabus Extractor.

Prunes promotional marketing boilerplate from catalog descriptions, extracting
substantive technical modules, tools, and hands-on lab learning outcomes to optimize
LLM context window efficiency and raise roadmap factual density.
"""
import re
from typing import Optional
from app.knowledge.models import VerifiedResource
from app.config import settings

# Regex patterns matching promotional fluff
FLUFF_PATTERNS = [
    r"(?i)join\s+(?:over\s+)?[\d,]+\+?\s*(?:students?|learners?|professionals?)",
    r"(?i)(?:30|14|7)[\s-]*day\s+money[\s-]*back\s+guarantee",
    r"(?i)enroll\s+(?:now|today|for\s+free)",
    r"(?i)rated\s+[\d\.]+\s*(?:out\s+of\s+5|\/\s*5|\s*stars)",
    r"(?i)certificate\s+of\s+completion\s+(?:included|provided)",
    r"(?i)lifetime\s+access\s+to\s+(?:all\s+)?materials",
    r"(?i)best[\s-]*selling\s+course",
    r"(?i)no\s+prior\s+experience\s+required",
    r"(?i)start\s+your\s+career\s+(?:today|in\s+tech)",
    r"(?i)downloadable\s+resources",
    r"(?i)special\s+discount\s+(?:available|offer)"
]

class ContextualCompressor:
    """Strips promotional boilerplate and extracts dense technical syllabus data."""

    def __init__(self):
        self.enabled = getattr(settings, "rag_enable_compressor", True)

    def compress_description(self, text: str) -> str:
        """Strip marketing boilerplate from a course or tutorial description."""
        if not self.enabled or not text:
            return text or ""

        cleaned = text
        for pattern in FLUFF_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # Normalize redundant spaces and punctuation artifacts
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+([,\.\?!])", r"\1", cleaned)
        cleaned = cleaned.strip()

        return cleaned

    def extract_dense_syllabus(self, resource: VerifiedResource) -> str:
        """
        Produce a compact, high-density syllabus summary for LLM context prompts.
        Extracts title, duration, difficulty, tools, and cleaned description.
        """
        title = getattr(resource, "title", "")
        platform = getattr(resource, "platform", "")
        skills = ", ".join(getattr(resource, "skills_covered", []))
        diff = getattr(resource, "difficulty", "beginner")
        diff_str = getattr(diff, "value", str(diff))
        dur = getattr(resource, "duration_hours", None)
        dur_str = f"{dur}h" if dur else "Self-paced"
        
        raw_desc = getattr(resource, "description", "")
        clean_desc = self.compress_description(raw_desc)

        return (
            f"[{platform}] {title} ({diff_str}, {dur_str}) | Skills: {skills} | "
            f"Core Curriculum: {clean_desc}"
        )

_COMPRESSOR_SINGLETON: Optional[ContextualCompressor] = None

def get_contextual_compressor() -> ContextualCompressor:
    """Singleton getter for ContextualCompressor."""
    global _COMPRESSOR_SINGLETON
    if _COMPRESSOR_SINGLETON is None:
        _COMPRESSOR_SINGLETON = ContextualCompressor()
    return _COMPRESSOR_SINGLETON

