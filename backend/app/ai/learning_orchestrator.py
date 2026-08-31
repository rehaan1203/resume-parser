"""Orchestrates the learning loop."""
from typing import Dict, Any, Optional
from datetime import datetime
from app.ai.feedback_collector import FeedbackCollector
from app.ai.pattern_extractor import PatternExtractor
from app.ai.knowledge_retriever import KnowledgeRetriever
from app.ai.knowledge_store import KnowledgeStore
from app.config import settings
from app.utils.logger import logger

class LearningOrchestrator:
    """Manages the continuous learning loop."""

    def __init__(self):
        self.feedback_collector = FeedbackCollector()
        self.pattern_extractor = PatternExtractor()
        self.knowledge_retriever = KnowledgeRetriever()
        self.knowledge_store = KnowledgeStore()
        self.enabled = settings.continuous_learning_enabled

    async def process_feedback(
        self,
        analysis_id: str,
        rating: int,
        comment: Optional[str] = None,
        corrections: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process feedback and extract patterns."""
        if not self.enabled:
            return {"processed": False, "reason": "Learning disabled"}

        try:
            # Step 1: Collect feedback
            feedback = await self.feedback_collector.collect_explicit(
                analysis_id=analysis_id,
                rating=rating,
                comment=comment,
                corrections=corrections
            )

            # Step 2: Extract patterns if corrections exist
            patterns = []
            if corrections and context:
                patterns = await self.pattern_extractor.extract_from_feedback(
                    feedback=feedback,
                    context=context
                )

                # Step 3: Store patterns
                for pattern in patterns:
                    await self.knowledge_store.save_pattern(pattern)

            return {
                "processed": True,
                "feedback_id": str(feedback.analysis_id), # Hack since feedback has no ID
                "patterns_extracted": len(patterns),
                "patterns": [p.dict() for p in patterns]
            }

        except Exception as e:
            logger.error(f"Failed to process feedback: {e}")
            return {"processed": False, "error": str(e)}

    async def process_implicit_feedback(
        self,
        analysis_id: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process implicit feedback."""
        if not self.enabled or not settings.implicit_feedback_enabled:
            return {"processed": False}

        try:
            feedback = await self.feedback_collector.collect_implicit(
                analysis_id=analysis_id,
                session_data=session_data
            )

            if feedback:
                return {"processed": True, "analysis_id": feedback.analysis_id, "rating": feedback.rating}
            else:
                return {"processed": False, "reason": "No implicit signal detected"}

        except Exception as e:
            logger.error(f"Failed to process implicit feedback: {e}")
            return {"processed": False, "error": str(e)}

    async def get_patterns_for_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get relevant patterns for a context."""
        if not self.enabled:
            return {"patterns": []}

        try:
            matches = await self.knowledge_retriever.retrieve(context, max_patterns=5)
            return {
                "patterns": [m.pattern.dict() for m in matches],
                "total_matches": len(matches)
            }
        except Exception as e:
            logger.error(f"Failed to retrieve patterns: {e}")
            return {"patterns": [], "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        if not self.enabled:
            return {"enabled": False}

        try:
            stats = await self.knowledge_store.get_stats()
            
            # Simple insights logic
            top_patterns = stats.top_patterns
            most_successful = top_patterns[0].id if top_patterns else None
            needs_improvement = next((p.id for p in top_patterns if p.success_count < p.failure_count), None)
            
            return {
                "enabled": True,
                "stats": stats.dict(),
                "insights": {
                    "most_successful_pattern": most_successful,
                    "needs_improvement": needs_improvement,
                    "accuracy_trend": "improving" if stats.pattern_success_rate > 0.5 else "declining",
                    "recommendation": "Focus on skill detection patterns" if not most_successful else "Keep generating feedback"
                }
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"enabled": True, "error": str(e)}
