"""Self-Querying & Constraint Filter Synthesizer.

Extracts structured query constraints (duration bounds, free/paid status, preferred platforms,
and credential types) from natural language candidate queries, enabling zero-loss attribute filtering
before dense vector scoring.
"""
import re
from typing import Optional, Dict, Any, List
from app.knowledge.models import QueryConstraints, VerifiedResource, ResourceType
from app.utils.logger import logger
from app.config import settings

class SelfQueryFilterSynthesizer:
    """Parses natural language requirements into structured QueryConstraints."""

    def __init__(self):
        self.enabled = getattr(settings, "rag_enable_self_query", True)

    def synthesize_constraints(
        self,
        query: str,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> QueryConstraints:
        """Parse natural language query and optional user preferences into QueryConstraints."""
        if not self.enabled:
            return QueryConstraints()

        clean = (query or "").lower()
        constraints = QueryConstraints()

        # 1. Negative Constraints & Anti-Skill Extraction (e.g., "no AWS", "without django", "exclude US")
        neg_matches = re.findall(r"(?:no|not|exclude|excluding|without)\s+([a-zA-Z0-9_\-\+]+)", clean)
        excluded_skills = []
        excluded_jurisdictions = []
        for term in neg_matches:
            term_clean = term.strip().lower()
            if term_clean in ("us", "usa", "united states"):
                excluded_jurisdictions.append("US")
            elif term_clean in ("in", "india", "indian"):
                excluded_jurisdictions.append("IN")
            elif term_clean in ("eu", "europe"):
                excluded_jurisdictions.append("EU")
            elif term_clean not in ("cost", "pay", "paying", "money", "limits"):
                excluded_skills.append(term_clean)

        constraints.excluded_skills = excluded_skills
        constraints.excluded_jurisdictions = excluded_jurisdictions

        # 2. Free vs Paid Detection
        if any(term in clean for term in ["free only", "free course", "no cost", "without paying", "free tutorial"]):
            constraints.is_free = True

        # 3. Duration Bound Extraction (e.g. "under 10 hours", "< 5 hrs", "less than 8 hours")
        duration_match = re.search(r"(?:under|less than|<)\s*(\d+(?:\.\d+)?)\s*(?:hours|hrs|hour|hr)", clean)
        if duration_match:
            try:
                constraints.max_duration_hours = float(duration_match.group(1))
            except (ValueError, TypeError):
                pass
        elif "quick" in clean or "short" in clean:
            constraints.max_duration_hours = 4.0

        # 4. Platform Preferences (skips platforms explicitly negated)
        platforms = []
        if ("youtube" in clean or "video" in clean) and "youtube" not in excluded_skills:
            platforms.append("YouTube")
        if "coursera" in clean and "coursera" not in excluded_skills:
            platforms.append("Coursera")
        if "edx" in clean and "edx" not in excluded_skills:
            platforms.append("edX")
        if "skill builder" in clean and "aws" not in excluded_skills:
            platforms.append("AWS Skill Builder")
        if "docs" in clean or "documentation" in clean:
            platforms.extend(["FastAPI Docs", "React Docs", "PyTorch.org", "Kubernetes.io"])
        constraints.required_platforms = platforms

        # 5. Resource Type Preferences
        allowed = []
        if any(term in clean for term in ["cert", "certification", "credential", "exam"]):
            allowed.append(ResourceType.CERTIFICATION.value)
        if any(term in clean for term in ["video", "watch", "youtube"]) and "youtube" not in excluded_skills:
            allowed.append(ResourceType.YOUTUBE_VIDEO.value)
        if any(term in clean for term in ["course", "class", "lecture"]):
            allowed.append(ResourceType.COURSE.value)
            if "youtube" in clean and "youtube" not in excluded_skills:
                allowed.append(ResourceType.YOUTUBE_VIDEO.value)
        if any(term in clean for term in ["docs", "documentation", "guide"]):
            allowed.append(ResourceType.DOCUMENTATION.value)
        constraints.allowed_types = list(set(allowed))

        # 6. Target Jurisdiction Auto-Inference via GeoRouter across ALL domains (Legal, Finance, Healthcare, Trades, Tech)
        from app.knowledge.geo_router import get_geo_router
        detected_jur = get_geo_router().detect_jurisdiction(clean)
        if detected_jur != "GLOBAL":
            constraints.target_jurisdiction = detected_jur

        # Merge explicit user preferences if provided
        if user_preferences:
            if "max_duration" in user_preferences:
                constraints.max_duration_hours = float(user_preferences["max_duration"])
            if "free_only" in user_preferences:
                constraints.is_free = bool(user_preferences["free_only"])
            if "target_jurisdiction" in user_preferences:
                constraints.target_jurisdiction = user_preferences["target_jurisdiction"]
            if "excluded_skills" in user_preferences:
                constraints.excluded_skills.extend(user_preferences["excluded_skills"])

        return constraints

    def matches_constraints(
        self,
        resource: VerifiedResource,
        constraints: QueryConstraints
    ) -> bool:
        """Evaluate if resource strictly fulfills extracted constraints."""
        if not self.enabled:
            return True

        # Check Free Status
        if constraints.is_free is True and getattr(resource, "is_free", True) is False:
            return False

        # Check Duration Limit
        if constraints.max_duration_hours is not None:
            res_dur = getattr(resource, "duration_hours", None)
            if res_dur is not None and res_dur > constraints.max_duration_hours:
                return False

        # Check Required Platform
        if constraints.required_platforms:
            res_platform = getattr(resource, "platform", "").lower()
            if not any(p.lower() in res_platform for p in constraints.required_platforms):
                return False

        # Check Allowed Types
        if constraints.allowed_types:
            res_type = getattr(resource, "type", "")
            type_str = getattr(res_type, "value", str(res_type)).lower()
            if not any(t.lower() == type_str for t in constraints.allowed_types):
                return False

        # Check Negative Anti-Skills
        if constraints.excluded_skills:
            res_skills = [s.lower() for s in getattr(resource, "skills_covered", [])]
            res_title = getattr(resource, "title", "").lower()
            for ex in constraints.excluded_skills:
                if any(ex == s or ex in s for s in res_skills) or ex in res_title:
                    logger.debug(f"SelfQuery: Resource '{resource.id}' excluded due to anti-skill '{ex}'")
                    return False

        # Check Excluded Jurisdictions
        if constraints.excluded_jurisdictions:
            res_jur = getattr(resource, "jurisdiction", "GLOBAL").strip().upper()
            ex_jurs = [j.strip().upper() for j in constraints.excluded_jurisdictions]
            if res_jur in ex_jurs:
                logger.debug(f"SelfQuery: Resource '{resource.id}' excluded due to jurisdiction '{res_jur}'")
                return False

        return True

_SYNTHESIZER_SINGLETON: Optional[SelfQueryFilterSynthesizer] = None

def get_self_query_synthesizer() -> SelfQueryFilterSynthesizer:
    """Singleton getter for SelfQueryFilterSynthesizer."""
    global _SYNTHESIZER_SINGLETON
    if _SYNTHESIZER_SINGLETON is None:
        _SYNTHESIZER_SINGLETON = SelfQueryFilterSynthesizer()
    return _SYNTHESIZER_SINGLETON
