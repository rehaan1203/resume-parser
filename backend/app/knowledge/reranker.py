"""Contextual Experience-Aware Reranker for RAG Learning Resources."""
from typing import List, Dict, Any, Optional
from app.knowledge.models import ResourceSearchResult, VerifiedResource
from app.utils.logger import logger
from app.config import settings

class ContextualReranker:
    """
    Reranks candidate learning resources based on candidate seniority,
    experience level, and career transition intent.
    Ensures juniors receive foundational materials and seniors receive depth/architectural tracks.
    """

    SENIORITY_DIFFICULTY_PREFERENCES = {
        "junior": {"beginner": 1.0, "intermediate": 0.8, "advanced": 0.4},
        "mid": {"beginner": 0.6, "intermediate": 1.0, "advanced": 0.8},
        "senior": {"beginner": 0.3, "intermediate": 0.8, "advanced": 1.0},
        "lead": {"beginner": 0.2, "intermediate": 0.7, "advanced": 1.0},
    }

    def __init__(self):
        self.enabled = getattr(settings, "rag_enable_reranker", True)

    def rerank(
        self,
        query: str,
        candidates: List[ResourceSearchResult],
        seniority: str = "mid",
        is_career_transition: bool = False,
        top_k: int = 2
    ) -> List[ResourceSearchResult]:
        """
        Rerank initial hybrid search candidates using candidate profile context.
        """
        if not self.enabled or not candidates:
            return candidates[:top_k]

        clean_seniority = (seniority or "mid").strip().lower()
        if clean_seniority not in self.SENIORITY_DIFFICULTY_PREFERENCES:
            if any(j in clean_seniority for j in ["entry", "intern", "junior", "associate", "student", "fresher"]):
                clean_seniority = "junior"
            elif any(s in clean_seniority for s in ["senior", "principal", "staff", "architect", "lead", "director", "manager"]):
                clean_seniority = "senior"
            else:
                clean_seniority = "mid"

        pref = self.SENIORITY_DIFFICULTY_PREFERENCES[clean_seniority]

        reranked: List[ResourceSearchResult] = []
        for item in candidates:
            res = getattr(item, "resource", item)
            item_score = getattr(item, "score", 0.8)
            item_skills = getattr(item, "matched_skills", getattr(res, "skills_covered", []))
            # Safely extract normalized difficulty string from enum or string
            raw_diff = getattr(res, "difficulty", "intermediate")
            diff_str = getattr(raw_diff, "value", str(raw_diff)).lower()
            if "beginner" in diff_str or "intro" in diff_str:
                res_diff = "beginner"
            elif "advanced" in diff_str or "expert" in diff_str:
                res_diff = "advanced"
            else:
                res_diff = "intermediate"

            diff_factor = pref.get(res_diff, 0.7)

            # Career switchers benefit from introductory foundations first regardless of prior seniority
            if is_career_transition:
                if res_diff == "beginner":
                    diff_factor = 1.25
                elif res_diff == "advanced":
                    diff_factor = 0.5

            # Senior practitioners benefit from credential/certification rigor
            res_type = getattr(res, "type", "")
            type_str = getattr(res_type, "value", str(res_type)).lower()
            cert_factor = 1.15 if (clean_seniority in ["senior", "lead"] and ("cert" in type_str or res_diff == "advanced")) else 1.0

            context_score = round(item_score * diff_factor * cert_factor, 4)
            reranked.append(ResourceSearchResult(
                resource=res,
                score=min(1.0, context_score),
                matched_skills=item_skills
            ))

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]

_GLOBAL_RERANKER: Optional[ContextualReranker] = None

def get_reranker() -> ContextualReranker:
    global _GLOBAL_RERANKER
    if _GLOBAL_RERANKER is None:
        _GLOBAL_RERANKER = ContextualReranker()
    return _GLOBAL_RERANKER
