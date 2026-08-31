"""Persistent storage for learning patterns and feedback."""
import json
import os
import uuid
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from app.models.domain_models import Pattern, Feedback, LearningStats
from app.config import settings
from app.utils.logger import logger

class KnowledgeStore:
    """Stores and retrieves learning data."""

    def __init__(self):
        self.store_path = Path(settings.learning_store_path)
        self._ensure_store_exists()

    def _ensure_store_exists(self):
        """Ensure the store directory and file exist."""
        if not os.path.exists(self.store_path.parent):
            os.makedirs(self.store_path.parent, exist_ok=True)
            
        if not self.store_path.exists():
            self._save_data({
                "patterns": [],
                "feedback": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            })

    def _load_data(self) -> Dict[str, Any]:
        """Load data from the store."""
        try:
            with open(self.store_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load learning data: {e}")
            return {"patterns": [], "feedback": [], "metadata": {}}

    def _save_data(self, data: Dict[str, Any]):
        """Save data to the store."""
        try:
            with open(self.store_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")

    async def save_pattern(self, pattern: Pattern):
        """Save a pattern to the store."""
        data = self._load_data()
        # Check if pattern already exists
        for i, p in enumerate(data["patterns"]):
            if p.get("id") == pattern.id:
                data["patterns"][i] = pattern.dict()
                break
        else:
            data["patterns"].append(pattern.dict())

        data["metadata"]["last_updated"] = datetime.now().isoformat()
        self._save_data(data)
        logger.info(f"Pattern saved: {pattern.id} ({pattern.type})")

    async def save_feedback(self, feedback: Feedback):
        """Save feedback to the store."""
        data = self._load_data()
        data["feedback"].append(feedback.dict())
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        self._save_data(data)
        logger.info(f"Feedback saved: {feedback.analysis_id}")

    async def get_patterns(self, pattern_type: Optional[str] = None) -> List[Pattern]:
        """Get patterns from the store."""
        data = self._load_data()
        patterns = data.get("patterns", [])
        if pattern_type:
            patterns = [p for p in patterns if p.get("type") == pattern_type]
            
        result = []
        for p in patterns:
            pattern = Pattern(**p)
            pattern = self._decay_confidence(pattern)
            result.append(pattern)
            
        return result

    def _decay_confidence(self, pattern: Pattern) -> Pattern:
        """Decay confidence over time."""
        days_since_update = (datetime.now() - pattern.updated_at).days
        if days_since_update > 30:
            months = days_since_update // 30
            # 5% decay per month
            decay_factor = 0.95 ** months
            pattern.confidence *= decay_factor
            
        return pattern

    async def get_feedback_for_analysis(self, analysis_id: str) -> List[Feedback]:
        """Get all feedback for a specific analysis."""
        data = self._load_data()
        feedback = [f for f in data.get("feedback", []) if f.get("analysis_id") == analysis_id]
        return [Feedback(**f) for f in feedback]

    async def get_stats(self) -> LearningStats:
        """Get learning statistics."""
        data = self._load_data()
        patterns = data.get("patterns", [])
        feedback = data.get("feedback", [])

        ratings = [f.get("rating") for f in feedback if f.get("rating") is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        successful_patterns = [p for p in patterns if p.get("success_count", 0) > p.get("failure_count", 0)]
        success_rate = len(successful_patterns) / len(patterns) if patterns else 0

        return LearningStats(
            total_patterns=len(patterns),
            total_feedback=len(feedback),
            average_rating=avg_rating,
            pattern_success_rate=success_rate,
            top_patterns=[Pattern(**p) for p in patterns[:5]],
            recent_feedback=[Feedback(**f) for f in feedback[-5:]],
            accuracy_trend=[],  # Calculate from ratings over time
            last_updated=datetime.now()
        )

    async def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern by ID."""
        data = self._load_data()
        original_count = len(data["patterns"])
        data["patterns"] = [p for p in data["patterns"] if p.get("id") != pattern_id]
        if len(data["patterns"]) < original_count:
            self._save_data(data)
            logger.info(f"Pattern deleted: {pattern_id}")
            return True
        return False
