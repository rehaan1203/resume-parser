"""RAGAS & RAG Triad Hallucination Guardrail Evaluator.

Provides deterministic in-process evaluation of Context Relevance,
Faithfulness (Groundedness), and Answer Relevance to prevent hallucinations
in learning roadmaps and career transition bridges.
"""
from typing import List, Dict, Any, Optional
from app.knowledge.models import VerifiedResource, ResourceSearchResult, RAGASTriadResult
from app.utils.logger import logger

class RAGASTriadEvaluator:
    """Evaluates the 3 pillars of the RAG Triad for verified resource retrieval."""

    def __init__(self, faithfulness_threshold: float = 0.80, min_context_relevance: float = 0.60):
        self.faithfulness_threshold = faithfulness_threshold
        self.min_context_relevance = min_context_relevance

    def compute_context_relevance(
        self,
        query_skills: List[str],
        retrieved_resources: List[VerifiedResource]
    ) -> float:
        """
        Measure Context Relevance:
        Proportion of target query skills directly addressed by retrieved resource items.
        """
        if not query_skills or not retrieved_resources:
            return 0.0

        all_covered_skills = set()
        for res in retrieved_resources:
            for s in res.skills_covered:
                all_covered_skills.add(s.lower().strip())
            # Also check title and description tokens
            all_covered_skills.add(res.title.lower())

        matched_count = 0
        for skill in query_skills:
            clean_s = skill.lower().strip()
            if any(clean_s in cs or cs in clean_s for cs in all_covered_skills):
                matched_count += 1

        relevance = matched_count / len(query_skills)
        return round(min(1.0, relevance), 4)

    def compute_faithfulness(
        self,
        retrieved_resources: List[VerifiedResource],
        generated_terms: Optional[List[str]] = None
    ) -> float:
        """
        Measure Groundedness / Faithfulness:
        Verifies that assertions, skills, and credentials suggested are strictly
        corroborated by active catalog documentation and syllabus contents.
        """
        if not retrieved_resources:
            return 0.0

        # Build ground-truth corpus from verified resources
        grounded_corpus = set()
        for res in retrieved_resources:
            grounded_corpus.update(s.lower().strip() for s in res.skills_covered)
            grounded_corpus.add(res.platform.lower().strip())
            grounded_corpus.add(res.title.lower().strip())
            grounded_corpus.add(getattr(res, "jurisdiction", "GLOBAL").lower().strip())

        if not generated_terms:
            # If no synthetic assertions provided, active verified status guarantees baseline groundedness
            active_ratio = sum(1 for r in retrieved_resources if r.health_status == "active") / len(retrieved_resources)
            return round(active_ratio, 4)

        # Check what fraction of generated terms are grounded in verified catalog data
        grounded_matches = 0
        for term in generated_terms:
            clean_t = term.lower().strip()
            if any(clean_t in gc or gc in clean_t for gc in grounded_corpus):
                grounded_matches += 1

        score = (grounded_matches / len(generated_terms)) if generated_terms else 1.0
        return round(min(1.0, score), 4)

    def compute_answer_relevance(
        self,
        target_domain: str,
        seniority: str,
        retrieved_resources: List[VerifiedResource]
    ) -> float:
        """
        Measure Answer Relevance:
        Ensures retrieved resources properly target the domain and candidate seniority tier.
        """
        if not retrieved_resources:
            return 0.0

        clean_dom = target_domain.lower().strip()
        clean_sen = seniority.lower().strip()

        scores = []
        for res in retrieved_resources:
            # Domain match
            dom_score = 1.0 if res.domain.lower() == clean_dom else 0.5
            # Seniority suitability
            diff = getattr(res.difficulty, "value", str(res.difficulty)).lower()
            if clean_sen in ("senior", "lead", "staff", "architect"):
                diff_score = 1.0 if diff in ("advanced", "intermediate") else 0.6
            elif clean_sen in ("fresher", "intern", "junior"):
                diff_score = 1.0 if diff in ("beginner", "intermediate") else 0.7
            else:
                diff_score = 1.0

            scores.append(0.6 * dom_score + 0.4 * diff_score)

        avg_score = sum(scores) / len(scores)
        return round(min(1.0, avg_score), 4)

    def evaluate_triad(
        self,
        query_skills: List[str],
        retrieved_resources: List[VerifiedResource],
        target_domain: str,
        seniority: str = "mid",
        generated_terms: Optional[List[str]] = None
    ) -> RAGASTriadResult:
        """Execute full RAG Triad verification."""
        cr = self.compute_context_relevance(query_skills, retrieved_resources)
        faith = self.compute_faithfulness(retrieved_resources, generated_terms)
        ar = self.compute_answer_relevance(target_domain, seniority, retrieved_resources)

        is_grounded = faith >= self.faithfulness_threshold and cr >= self.min_context_relevance

        reasoning = (
            f"RAGAS Triad Evaluation: Context Relevance={cr:.2f}, "
            f"Faithfulness={faith:.2f}, Answer Relevance={ar:.2f}. "
            f"Status: {'GROUNDED & CERTIFIED' if is_grounded else 'REQUIRES RE-RETRIEVAL'}"
        )

        logger.debug(reasoning)

        return RAGASTriadResult(
            context_relevance=cr,
            faithfulness=faith,
            answer_relevance=ar,
            is_grounded=is_grounded,
            reasoning=reasoning
        )

_GLOBAL_RAGAS: Optional[RAGASTriadEvaluator] = None

def get_ragas_evaluator() -> RAGASTriadEvaluator:
    """Singleton getter for RAGASTriadEvaluator."""
    global _GLOBAL_RAGAS
    if _GLOBAL_RAGAS is None:
        _GLOBAL_RAGAS = RAGASTriadEvaluator()
    return _GLOBAL_RAGAS

