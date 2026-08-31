"""Extracts patterns from feedback and interactions."""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from app.models.domain_models import Pattern, Feedback
from app.ai.knowledge_store import KnowledgeStore
from app.utils.logger import logger

class PatternExtractor:
    """Extracts learning patterns from feedback."""

    def __init__(self):
        self.store = KnowledgeStore()

    async def extract_from_feedback(self, feedback: Feedback, context: Dict[str, Any]) -> List[Pattern]:
        """Extract patterns from a single feedback."""
        patterns = []

        # Pattern 1: Domain mismatch correction
        if feedback.correction and "domain" in feedback.correction:
            patterns.append(await self._extract_domain_pattern(feedback, context))

        # Pattern 2: Skill detection correction
        if feedback.correction and "skills" in feedback.correction:
            patterns.append(await self._extract_skill_pattern(feedback, context))

        # Pattern 3: Scoring correction
        if feedback.correction and "score" in feedback.correction:
            patterns.append(await self._extract_scoring_pattern(feedback, context))

        return patterns

    async def _extract_domain_pattern(self, feedback: Feedback, context: Dict[str, Any]) -> Pattern:
        """Extract domain-related pattern."""
        return Pattern(
            id=f"domain_{uuid.uuid4().hex[:8]}",
            type="domain_detection",
            context={
                "resume_domain": context.get("resume_domain"),
                "jd_domain": context.get("jd_domain"),
                "keywords": context.get("keywords", [])
            },
            rule=feedback.correction.get("domain_rule", "Domain mismatch should be penalized"),
            confidence=0.7 if feedback.rating >= 4 else 0.3
        )

    async def _extract_skill_pattern(self, feedback: Feedback, context: Dict[str, Any]) -> Pattern:
        """Extract skill-related pattern."""
        return Pattern(
            id=f"skill_{uuid.uuid4().hex[:8]}",
            type="skill_detection",
            context={
                "skill_keyword": context.get("skill_keyword"),
                "domain": context.get("domain")
            },
            rule=feedback.correction.get("skill_rule", "Infer skill from keyword"),
            confidence=0.7 if feedback.rating >= 4 else 0.3
        )

    async def _extract_scoring_pattern(self, feedback: Feedback, context: Dict[str, Any]) -> Pattern:
        """Extract scoring-related pattern."""
        return Pattern(
            id=f"score_{uuid.uuid4().hex[:8]}",
            type="scoring_rule",
            context={
                "score_range": context.get("score_range"),
                "domain_match": context.get("domain_match")
            },
            rule=feedback.correction.get("scoring_rule", "Adjust scoring based on domain"),
            confidence=0.7 if feedback.rating >= 4 else 0.3
        )

    async def update_pattern_confidence(self, pattern: Pattern, feedback: Feedback) -> Pattern:
        """Update pattern confidence based on new feedback."""
        if feedback.rating >= 4:
            pattern.success_count += 1
        elif feedback.rating <= 2:
            pattern.failure_count += 1

        # Calculate new confidence
        total = pattern.success_count + pattern.failure_count
        if total > 0:
            pattern.confidence = pattern.success_count / total

        pattern.updated_at = datetime.now()
        pattern.version += 1
        return pattern
