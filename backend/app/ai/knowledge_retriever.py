"""Retrieves relevant patterns for a given context."""
from typing import List, Dict, Any, Optional
from app.models.domain_models import Pattern, PatternMatch
from app.ai.knowledge_store import KnowledgeStore
from app.utils.logger import logger

class KnowledgeRetriever:
    """Retrieves relevant patterns for a context."""

    def __init__(self):
        self.store = KnowledgeStore()

    async def retrieve(
        self,
        context: Dict[str, Any],
        max_patterns: int = 5
    ) -> List[PatternMatch]:
        """Retrieve patterns matching the given context."""
        all_patterns = await self.store.get_patterns()
        matches = []

        for pattern in all_patterns:
            if pattern.deprecated:
                continue
                
            relevance = self._calculate_relevance(pattern, context)
            if relevance > 0.3:  # Only include relevant patterns
                matches.append(PatternMatch(
                    pattern=pattern,
                    relevance_score=relevance,
                    context_overlap=self._find_overlap(pattern.context, context)
                ))

        # Sort by relevance
        matches.sort(key=lambda x: x.relevance_score, reverse=True)
        return matches[:max_patterns]

    def _calculate_relevance(self, pattern: Pattern, context: Dict[str, Any]) -> float:
        """Calculate relevance score between pattern and context."""
        overlap_count = 0
        total_keys = len(pattern.context.keys())

        for key, value in pattern.context.items():
            if key in context and context[key] == value:
                overlap_count += 1

        if total_keys == 0:
            return 0

        base_relevance = overlap_count / total_keys
        # Boost by confidence
        return base_relevance * pattern.confidence

    def _find_overlap(self, pattern_context: Dict, context: Dict) -> List[str]:
        """Find overlapping keys between pattern and context."""
        overlap = []
        for key in pattern_context.keys():
            if key in context:
                overlap.append(key)
        return overlap

    async def get_examples_for_few_shot(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get examples for few-shot prompting."""
        matches = await self.retrieve(context, max_patterns=2)
        examples = []

        for match in matches:
            if match.pattern.type == "domain_detection":
                success_rate = match.pattern.success_count / (match.pattern.success_count + match.pattern.failure_count + 1)
                examples.append({
                    "context": match.pattern.context,
                    "rule": match.pattern.rule,
                    "success_rate": round(success_rate, 2)
                })

        return examples
