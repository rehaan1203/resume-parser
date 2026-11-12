"""Recency-Aware RAG Scorer & Technology Depreciation Guard.

Calculates time-decay penalties for learning resources using domain-adaptive
half-life decay functions. Automatically penalizes obsolete tutorials in fast-moving
fields (e.g. Python 2, React class components, old cloud SDKs) while preserving evergreen
foundational principles in law, accounting, and trades safety.
"""
import math
from typing import Optional
from app.knowledge.models import VerifiedResource
from app.config import settings
from app.utils.logger import logger

CURRENT_YEAR = 2026

class RecencyScorer:
    """Calculates recency multipliers and deprecation status for learning resources."""

    # Domain decay rate constants (lambda)
    # Tech / ML moves very fast; Law, GAAP Accounting, and Core Trades are evergreen
    DOMAIN_DECAY_RATES = {
        "tech": 0.28,                # Half-life ~2.5 years
        "software_engineering": 0.28,
        "data_science": 0.25,        # Half-life ~2.8 years
        "finance": 0.10,             # Half-life ~7.0 years
        "healthcare": 0.12,          # Half-life ~5.8 years
        "legal": 0.05,               # Half-life ~14.0 years (evergreen statutory concepts)
        "trades": 0.06               # Half-life ~11.5 years (Ohm's law, thermodynamics)
    }

    # Maximum age before a resource is considered legacy in fast-moving domains
    DEPRECATION_AGE_THRESHOLD = 4

    def __init__(self):
        self.enabled = getattr(settings, "rag_enable_recency_scorer", True)

    def calculate_recency_multiplier(
        self,
        resource: VerifiedResource,
        current_year: int = CURRENT_YEAR
    ) -> float:
        """
        Compute an exponential recency multiplier between 0.2 and 1.0.
        multiplier = exp(-lambda * delta_years)
        """
        if not self.enabled:
            return 1.0

        pub_year = getattr(resource, "publication_year", None) or current_year
        delta_years = max(0, current_year - pub_year)

        domain = getattr(resource, "domain", "tech").lower()
        decay_rate = self.DOMAIN_DECAY_RATES.get(domain, 0.20)

        multiplier = math.exp(-decay_rate * delta_years)
        # Clamp multiplier between 0.30 and 1.0 to avoid complete blackout of still-useful content
        clamped = max(0.30, min(1.0, round(multiplier, 4)))
        return clamped

    def is_deprecated(
        self,
        resource: VerifiedResource,
        current_year: int = CURRENT_YEAR
    ) -> bool:
        """Returns True if a fast-moving tech resource exceeds the age threshold."""
        domain = getattr(resource, "domain", "tech").lower()
        if domain not in ["tech", "software_engineering", "data_science"]:
            return False

        pub_year = getattr(resource, "publication_year", None) or current_year
        return (current_year - pub_year) >= self.DEPRECATION_AGE_THRESHOLD

_RECENCY_SINGLETON: Optional[RecencyScorer] = None

def get_recency_scorer() -> RecencyScorer:
    """Singleton getter for RecencyScorer."""
    global _RECENCY_SINGLETON
    if _RECENCY_SINGLETON is None:
        _RECENCY_SINGLETON = RecencyScorer()
    return _RECENCY_SINGLETON

