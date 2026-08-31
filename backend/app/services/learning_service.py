"""Learning service for the main application."""
from typing import Dict, Any, Optional
from app.ai.learning_orchestrator import LearningOrchestrator
from app.utils.logger import logger

class LearningService:
    """Service layer for learning operations."""

    def __init__(self):
        self.orchestrator = LearningOrchestrator()

    async def process_analysis_feedback(
        self,
        analysis_id: str,
        analysis_result: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process feedback for an analysis."""
        if not user_feedback:
            return {"processed": False, "reason": "No feedback provided"}

        # Extract context from analysis result
        context = {
            "resume_domain": analysis_result.get("resume_domain"),
            "jd_domain": analysis_result.get("jd_domain"),
            "score": analysis_result.get("overall_score"),
            "keywords": analysis_result.get("skill_gaps", [])[:5]
        }

        # Process the feedback
        result = await self.orchestrator.process_feedback(
            analysis_id=analysis_id,
            rating=user_feedback.get("rating", 3),
            comment=user_feedback.get("comment"),
            corrections=user_feedback.get("corrections"),
            context=context
        )

        return result

    async def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from the learning system."""
        stats = await self.orchestrator.get_stats()
        return {
            "insights": {
                "total_learned_patterns": stats.get("stats", {}).get("total_patterns", 0),
                "average_user_rating": stats.get("stats", {}).get("average_rating", 0),
                "pattern_success_rate": stats.get("stats", {}).get("pattern_success_rate", 0)
            }
        }
