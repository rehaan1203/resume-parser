"""Learning memory for storing and retrieving patterns."""
import json
from typing import Dict, Any, List
from pathlib import Path
from app.config import settings
from loguru import logger
from datetime import datetime

class MemoryStore:
    """Store and retrieve learning patterns."""

    def __init__(self):
        self.enabled = settings.learning_memory_enabled
        self.store_type = settings.learning_store_type
        self.store_path = Path(settings.learning_store_path)

        if self.store_type == "file":
            self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure the memory file exists."""
        if not self.store_path.exists():
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_memory({"patterns": [], "corrections": []})

    def _load_memory(self) -> Dict[str, Any]:
        """Load memory from file."""
        if not self.store_path.exists():
            return {"patterns": [], "corrections": []}

        try:
            with open(self.store_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            return {"patterns": [], "corrections": []}

    def _save_memory(self, memory: Dict[str, Any]):
        """Save memory to file."""
        try:
            with open(self.store_path, 'w') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    async def find_matching_patterns(
        self,
        resume: str,
        jd: str
    ) -> List[Dict[str, Any]]:
        """Find patterns that match the current context."""
        if not self.enabled or self.store_type != "file":
            return []

        memory = self._load_memory()
        patterns = memory.get("patterns", [])

        # Simple keyword-based matching
        resume_keywords = set(resume.lower().split()[:50])
        jd_keywords = set(jd.lower().split()[:50])

        matched = []
        for pattern in patterns:
            pattern_keywords = set(pattern.get("keywords", []))
            overlap = len(pattern_keywords & resume_keywords) + len(pattern_keywords & jd_keywords)
            if overlap > 2:  # Threshold for match
                matched.append(pattern)

        return matched[:3]  # Limit to top 3 matches

    async def store_correction(self, correction: Dict[str, Any]):
        """Store a correction for future learning."""
        if not self.enabled or self.store_type != "file":
            return

        memory = self._load_memory()
        memory["corrections"].append(correction)

        # Extract pattern from correction
        writer_output = correction.get("writer_output", {})
        corrected_output = correction.get("correction", {})

        pattern = {
            "name": f"Correction_{len(memory['corrections'])}",
            "keywords": writer_output.get("skill_gaps", [])[:3] if isinstance(writer_output, dict) else [],
            "original_score": writer_output.get("overall_score", 0) if isinstance(writer_output, dict) else 0,
            "corrected_score": corrected_output.get("overall_score", 0),
            "timestamp": str(datetime.now())
        }
        memory["patterns"].append(pattern)

        self._save_memory(memory)
        logger.info(f"Stored correction with pattern: {pattern['name']}")

    async def get_stats(self) -> Dict[str, int]:
        """Get memory statistics."""
        if self.store_type != "file":
             return {"patterns": 0, "corrections": 0}
        memory = self._load_memory()
        return {
            "patterns": len(memory.get("patterns", [])),
            "corrections": len(memory.get("corrections", []))
        }
