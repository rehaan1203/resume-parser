"""Collects explicit and implicit user feedback."""
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.domain_models import Feedback
from app.ai.knowledge_store import KnowledgeStore
from app.utils.logger import logger
from app.config import settings

class FeedbackCollector:
    """Collects and processes user feedback."""

    def __init__(self):
        self.store = KnowledgeStore()
        self.implicit_enabled = settings.implicit_feedback_enabled

    async def collect_explicit(
        self,
        analysis_id: str,
        rating: int,
        comment: Optional[str] = None,
        corrections: Optional[Dict[str, Any]] = None
    ) -> Feedback:
        """Collect explicit user feedback."""
        feedback = Feedback(
            analysis_id=analysis_id,
            rating=rating,
            comment=comment,
            correction=corrections,
            feedback_type="explicit"
        )

        await self.store.save_feedback(feedback)
        logger.info(f"Explicit feedback collected: analysis={analysis_id}, rating={rating}")
        return feedback

    async def collect_implicit(
        self,
        analysis_id: str,
        session_data: Dict[str, Any]
    ) -> Optional[Feedback]:
        """Collect implicit feedback from user behavior."""
        if not self.implicit_enabled:
            return None

        rating = self._calculate_implicit_rating(session_data)
        if rating is None:
            return None

        feedback = Feedback(
            analysis_id=analysis_id,
            rating=rating,
            comment=None,
            correction=None,
            feedback_type="implicit"
        )

        await self.store.save_feedback(feedback)
        logger.info(f"Implicit feedback collected: analysis={analysis_id}, rating={rating}")
        return feedback

    def _calculate_implicit_rating(self, session_data: Dict[str, Any]) -> Optional[int]:
        """Calculate rating from implicit signals."""
        # Example: Re-submission indicates dissatisfaction
        if session_data.get("resubmitted", False):
            return 1

        # Example: Long time on results indicates engagement
        time_spent = session_data.get("time_spent_seconds", 0)
        if time_spent > 120:
            return 4

        # Example: Scrolled to bottom indicates completion
        if session_data.get("scrolled_to_bottom", False):
            return 5

        return None

    async def get_feedback_stats(self, analysis_id: str) -> Dict[str, Any]:
        """Get feedback statistics for an analysis."""
        feedbacks = await self.store.get_feedback_for_analysis(analysis_id)
        if not feedbacks:
            return {"count": 0, "average_rating": None}

        ratings = [f.rating for f in feedbacks]
        return {
            "count": len(feedbacks),
            "average_rating": sum(ratings) / len(ratings),
            "min_rating": min(ratings),
            "max_rating": max(ratings)
        }
