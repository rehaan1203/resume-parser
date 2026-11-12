"""Corrective RAG (CRAG) Evaluator & Quality Grader.

Active self-evaluation layer that grades retrieved learning resources against candidate
skill gap intent, filters noisy or misaligned candidates, transforms struggling queries,
and ensures roadmap recommendations remain strictly grounded and hallucination-free.
"""
from typing import List, Tuple, Optional, Set
from app.knowledge.models import VerifiedResource, ResourceSearchResult, CRAGGrade
from app.utils.logger import logger
from app.config import settings

class CRAGEvaluator:
    """Evaluates and grades candidate resources to guarantee retrieval accuracy."""

    _CLOUD_VENDOR_KEYWORDS = {
        "azure": ("azure", "microsoft learn", "entra", "blob storage", "application insights"),
        "aws": ("aws", "amazon web services", "ec2", "s3", "skillbuilder", "cloudfront", "dynamodb"),
        "gcp": ("gcp", "google cloud", "bigquery", "vertex ai", "cloud run", "google ai"),
    }

    def __init__(self):
        self.enabled = getattr(settings, "rag_enable_crag", True)
        self.min_confidence = getattr(settings, "crag_min_confidence", 0.40)

    @classmethod
    def extract_vendors(cls, text: str) -> Set[str]:
        """Extract explicit cloud ecosystem tags referenced in free-form skill or JD text."""
        import re
        q = (text or "").lower()
        return {
            vendor
            for vendor, kws in cls._CLOUD_VENDOR_KEYWORDS.items()
            if any(re.search(rf"\b{re.escape(kw)}\b", q) for kw in kws)
        }

    @classmethod
    def _detect_vendor_conflict(
        cls,
        query_skill: str,
        resource: VerifiedResource,
        preferred_vendors: Optional[Set[str]] = None,
    ) -> bool:
        """Return True if query/batch targets specific cloud ecosystem(s) and resource targets a competing cloud."""
        query_vendors = cls.extract_vendors(query_skill)
        active_vendors = query_vendors if query_vendors else (preferred_vendors or set())
        if not active_vendors:
            return False

        res_text = " ".join([
            getattr(resource, "title", ""),
            getattr(resource, "platform", ""),
            " ".join(getattr(resource, "skills_covered", [])),
        ])
        res_vendors = cls.extract_vendors(res_text)
        return bool(res_vendors and res_vendors.isdisjoint(active_vendors))

    def grade_resource(
        self,
        resource: VerifiedResource,
        query_skill: str,
        seniority: str = "mid",
        domain: Optional[str] = None,
        preferred_vendors: Optional[Set[str]] = None,
    ) -> CRAGGrade:
        """
        Grade a candidate resource as 'correct', 'ambiguous', or 'incorrect'.
        Evaluates title/description match, skill coverage, vendor affinity, and domain coherence.
        """
        if self._detect_vendor_conflict(query_skill, resource, preferred_vendors=preferred_vendors):
            return CRAGGrade(
                resource_id=getattr(resource, "id", "unknown"),
                grade="incorrect",
                confidence=0.0,
                reason="Cloud ecosystem mismatch with requested skill",
            )

        clean_query = query_skill.strip().lower()
        res_skills = [s.strip().lower() for s in getattr(resource, "skills_covered", [])]
        res_title = getattr(resource, "title", "").lower()
        res_desc = getattr(resource, "description", "").lower()
        res_domain = getattr(resource, "domain", "").lower()

        score = 0.0
        reasons = []

        # 1. Direct skill tag match (strongest signal)
        if any(clean_query in s or s in clean_query for s in res_skills):
            score += 0.50
            reasons.append("Exact skill tag overlap")
        elif any(part in " ".join(res_skills) for part in clean_query.split()):
            score += 0.30
            reasons.append("Partial skill tag overlap")

        # 2. Title & Description keyword density
        if clean_query in res_title:
            score += 0.30
            reasons.append("Skill keyword present in resource title")
        elif any(part in res_title for part in clean_query.split() if len(part) > 2):
            score += 0.15
            reasons.append("Token match in resource title")

        if clean_query in res_desc:
            score += 0.20
            reasons.append("Skill keyword present in description")

        # 3. Domain consistency check
        if domain and res_domain:
            norm_tgt = domain.lower().replace("software_engineering", "tech").replace("data_science", "tech")
            norm_res = res_domain.lower().replace("software_engineering", "tech").replace("data_science", "tech")
            if norm_tgt == norm_res:
                score += 0.15
                reasons.append("Domain match")
            else:
                score -= 0.10
                reasons.append("Domain mismatch penalty")

        # 4. Seniority / difficulty calibration
        raw_diff = getattr(resource, "difficulty", "intermediate")
        diff_str = getattr(raw_diff, "value", str(raw_diff)).lower()
        clean_sen = (seniority or "mid").lower()

        if clean_sen in ["entry", "fresher", "junior"] and "beginner" in diff_str:
            score += 0.10
            reasons.append("Beginner resource aligned with junior seniority")
        elif clean_sen in ["senior", "lead"] and ("advanced" in diff_str or "cert" in getattr(resource, "type", "").lower()):
            score += 0.10
            reasons.append("Advanced credential aligned with senior seniority")

        # Normalize score
        final_confidence = min(max(round(score, 3), 0.0), 1.0)

        # Classification thresholds
        if final_confidence >= 0.70:
            classification = "correct"
        elif final_confidence >= self.min_confidence:
            classification = "ambiguous"
        else:
            classification = "incorrect"

        return CRAGGrade(
            resource_id=getattr(resource, "id", "unknown"),
            grade=classification,
            confidence=final_confidence,
            reason="; ".join(reasons) if reasons else "Low semantic correlation"
        )

    def filter_and_evaluate(
        self,
        candidates: List[ResourceSearchResult],
        query_skill: str,
        seniority: str = "mid",
        domain: Optional[str] = None,
        preferred_vendors: Optional[Set[str]] = None,
    ) -> Tuple[List[ResourceSearchResult], List[CRAGGrade], bool]:
        """
        Evaluate all candidates, prune incorrect items, and signal if fallback is required.
        Returns: (certified_candidates, all_grades, needs_query_transformation_or_fallback)
        """
        if not self.enabled or not candidates:
            return candidates, [], False

        certified: List[ResourceSearchResult] = []
        grades: List[CRAGGrade] = []

        for item in candidates:
            res = getattr(item, "resource", item)
            grade = self.grade_resource(
                res,
                query_skill,
                seniority=seniority,
                domain=domain,
                preferred_vendors=preferred_vendors,
            )
            grades.append(grade)

            if grade.grade in ["correct", "ambiguous"]:
                certified.append(item)
            else:
                logger.debug(f"CRAG: Pruned incorrect candidate '{getattr(res, 'title', '')}' (confidence: {grade.confidence})")

        needs_fallback = len(certified) == 0
        return certified, grades, needs_fallback

    def transform_query(self, original_query: str, domain: Optional[str] = None, seniority: str = "mid") -> str:
        """
        Query Rewriting / Reformulation step:
        Transforms an ambiguous or failing query into a focused search query.
        """
        clean = original_query.strip()
        clean_sen = (seniority or "mid").lower()

        if clean_sen in ["entry", "fresher", "junior"]:
            return f"{clean} fundamentals beginner course tutorial"
        elif clean_sen in ["senior", "lead"]:
            return f"{clean} advanced architecture professional certification guide"
        else:
            return f"{clean} complete guide practical hands-on course"

_CRAG_SINGLETON: Optional[CRAGEvaluator] = None

def get_crag_evaluator() -> CRAGEvaluator:
    """Singleton getter for CRAGEvaluator."""
    global _CRAG_SINGLETON
    if _CRAG_SINGLETON is None:
        _CRAG_SINGLETON = CRAGEvaluator()
    return _CRAG_SINGLETON

