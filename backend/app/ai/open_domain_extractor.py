"""Open-Domain Requirement Extractor Service (D4 Specification)."""
import re
import json
from typing import List, Dict, Any, Optional
from app.models.open_domain_models import (
    RequirementCategory,
    ImportanceTier,
    ExtractedRequirement,
    CandidateRequirementMatch,
    OpenDomainAnalysisResult,
    IMPORTANCE_WEIGHTS
)
from app.utils.score_calculator import calculate_open_domain_weighted_score
from app.prompts.open_domain_prompt import (
    build_open_domain_jd_prompt,
    build_open_domain_matching_prompt
)
from app.ai.client import GenAIClient
from app.utils.logger import logger
from app.utils.skill_extractor import extract_open_domain_skills
from app.knowledge.taxonomy_service import get_taxonomy_service

class OpenDomainExtractor:
    """Multi-domain requirement extractor and match evaluator."""

    def __init__(self, client: Optional[GenAIClient] = None):
        self.client = client
        self.last_detected_domain: Optional[str] = None

    def remap_non_numeric_durations(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        D1/D4 Rule: Non-numeric duration requirements (e.g. 'clean driving record',
        'pass physical exam') incorrectly tagged as durations must be remapped to 'skill' or 'credential'.
        Numeric durations are categorized as 'domain_experience'.
        """
        remapped = []
        duration_keywords = re.compile(
            r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|decade|decades)\+?\s*(?:years?|yrs?|months?)\b',
            re.IGNORECASE
        )
        for req in requirements:
            cat = req.get("category", "skill")
            name = req.get("name", "")
            raw = req.get("raw_text", "")
            text_to_check = f"{name} {raw}"

            if cat in ("domain_experience", "experience_duration"):
                if duration_keywords.search(text_to_check):
                    req["category"] = RequirementCategory.DOMAIN_EXPERIENCE.value
                else:
                    if re.search(r'\b(?:license|certification|credential|exam|bar|clearance|record)\b', text_to_check, re.IGNORECASE):
                        req["category"] = RequirementCategory.CREDENTIAL.value
                    else:
                        req["category"] = RequirementCategory.SKILL.value

            remapped.append(req)
        return remapped

    def extract_deterministic_requirements(self, jd_text: str) -> List[Dict[str, Any]]:
        """Fallback rule-based extraction across Tech, Healthcare, Trades, and Legal."""
        extracted_skills = extract_open_domain_skills(jd_text)
        requirements = []
        for s in extracted_skills:
            s_lower = s.lower()
            if s_lower in ("bls", "acls", "cpr", "rn", "epa 608", "osha", "pmp", "cpa"):
                cat = RequirementCategory.CREDENTIAL.value
            elif s_lower in ("docker", "kubernetes", "epic", "lexisnexis", "ehr", "salesforce"):
                cat = RequirementCategory.TOOL.value
            else:
                cat = RequirementCategory.SKILL.value

            requirements.append({
                "name": s,
                "category": cat,
                "importance": ImportanceTier.MUST_HAVE.value,
                "raw_text": s
            })
        return requirements

    async def extract_requirements(self, jd_text: str) -> List[Dict[str, Any]]:
        """Extract open-domain requirements and role specialization using Redis-cached LLM with deterministic fallback."""
        self.last_detected_domain = None
        if not jd_text:
            return []

        if self.client:
            import hashlib
            from app.config import settings
            from app.utils.cache_manager import CacheManager
            from app.prompts.open_domain_prompt import OPEN_DOMAIN_REQUIREMENTS_PROMPT_VERSION

            jd_hash = hashlib.sha256(jd_text.strip().encode("utf-8")).hexdigest()[:16]
            cache_key = f"od_jd:{OPEN_DOMAIN_REQUIREMENTS_PROMPT_VERSION}:{jd_hash}"
            cache_mgr = CacheManager()

            if getattr(settings, "cache_enabled", True):
                try:
                    cached = await cache_mgr.get(cache_key)
                    if isinstance(cached, dict) and cached.get("requirements"):
                        self.last_detected_domain = cached.get("domain")
                        return self.remap_non_numeric_durations(list(cached["requirements"]))
                except Exception:
                    pass

            try:
                prompt = build_open_domain_jd_prompt(jd_text)
                schema = {
                    "domain": "string",
                    "requirements": [
                        {
                            "name": "string",
                            "category": "string",
                            "importance": "string",
                            "raw_text": "string"
                        }
                    ]
                }
                res = await self.client.generate_structured_content(prompt, schema)
                if isinstance(res, list):
                    raw_reqs = res
                elif isinstance(res, dict):
                    dom = res.get("domain")
                    if isinstance(dom, str) and dom.strip():
                        self.last_detected_domain = dom.strip()
                    raw_reqs = res.get("requirements", [])
                else:
                    raw_reqs = []

                if isinstance(raw_reqs, list) and raw_reqs:
                    cleaned = [r for r in raw_reqs if isinstance(r, dict) and r.get("name")]
                    if cleaned:
                        remapped = self.remap_non_numeric_durations(cleaned)
                        if getattr(settings, "cache_enabled", True):
                            try:
                                await cache_mgr.set(
                                    cache_key,
                                    {"domain": self.last_detected_domain, "requirements": remapped},
                                    ttl=getattr(settings, "cache_ttl_jd", 604800),
                                )
                            except Exception:
                                pass
                        return remapped
            except Exception as e:
                logger.warning(f"LLM open-domain extraction fallback to deterministic: {e}")

        deterministic = self.extract_deterministic_requirements(jd_text)
        return self.remap_non_numeric_durations(deterministic)

    async def evaluate_matches(
        self,
        requirements: List[Dict[str, Any]],
        resume_text: str
    ) -> OpenDomainAnalysisResult:
        """Evaluate candidate fulfillment and compute weighted D4 score."""
        if not requirements:
            return OpenDomainAnalysisResult(
                requirements=[],
                matches=[],
                weighted_score=0.0,
                category_breakdown={},
                skill_gaps=[],
                strengths=[]
            )

        matches: List[Dict[str, Any]] = []
        resume_lower = resume_text.lower() if resume_text else ""
        taxonomy = get_taxonomy_service()

        def _safe_category(val: Any) -> RequirementCategory:
            raw = str(val or "skill").strip().lower()
            try:
                return RequirementCategory(raw)
            except ValueError:
                if any(k in raw for k in ("cert", "licens", "cred", "bar", "clear")):
                    return RequirementCategory.CREDENTIAL
                if any(k in raw for k in ("deg", "edu", "bachelor", "master", "phd")):
                    return RequirementCategory.EDUCATION
                if any(k in raw for k in ("tool", "soft", "plat", "frame", "device", "system")):
                    return RequirementCategory.TOOL
                if any(k in raw for k in ("lead", "manag", "mentor")):
                    return RequirementCategory.LEADERSHIP
                if "exp" in raw or "domain" in raw:
                    return RequirementCategory.DOMAIN_EXPERIENCE
                return RequirementCategory.SKILL

        def _safe_importance(val: Any) -> ImportanceTier:
            raw = str(val or "must_have").strip().lower()
            try:
                return ImportanceTier(raw)
            except ValueError:
                if "pref" in raw or "desir" in raw:
                    return ImportanceTier.PREFERRED
                if "bon" in raw or "opt" in raw or "nice" in raw:
                    return ImportanceTier.BONUS
                return ImportanceTier.MUST_HAVE

        _token_stop = {"with", "and", "for", "the", "from", "into", "over", "skills", "experience", "knowledge", "years", "year", "yrs", "minimum", "plus"}

        # Precompute max explicit year claim in resume when verifying numeric duration requirements
        resume_year_nums = [int(y) for y in re.findall(r'\b(\d+)\+?\s*(?:years?|yrs?)\b', resume_lower) if y.isdigit()]
        max_resume_stated_yrs = max(resume_year_nums) if resume_year_nums else 0

        for req in requirements:
            name = str(req["name"]).strip()
            name_lower = name.lower()
            canonical_req = taxonomy.normalize_term(name_lower)
            cat_enum = _safe_category(req.get("category", "skill"))
            imp_enum = _safe_importance(req.get("importance", "must_have"))

            # Normalize sanitized requirement back so score_calculator uses canonical strings
            req["category"] = cat_enum.value
            req["importance"] = imp_enum.value

            # Enforce numeric year requirement threshold before awarding keyword match on duration requirements
            dur_req_m = re.search(r'\b(\d+)\+?\s*(?:years?|yrs?)\b', name_lower)
            if dur_req_m and max_resume_stated_yrs < int(dur_req_m.group(1)):
                matches.append({
                    "requirement_name": name,
                    "category": cat_enum.value,
                    "importance": imp_enum.value,
                    "credit": 0.0,
                    "status": "missing",
                    "evidence_quote": None,
                })
                continue

            # Direct match or canonical synonym match in resume
            if (
                re.search(r'(?<!\w)' + re.escape(name_lower) + r'(?!\w)', resume_lower)
                or (canonical_req and re.search(r'(?<!\w)' + re.escape(canonical_req) + r'(?!\w)', resume_lower))
            ):
                credit = 1.0
                status = "matched"
                quote = name
            else:
                tokens = [
                    t for t in re.findall(r"[a-z0-9\+\#]{2,}", name_lower)
                    if t not in _token_stop and not re.fullmatch(r'\d+\+?', t)
                ]
                matched_toks = [
                    t for t in tokens
                    if re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', resume_lower)
                ]
                if tokens and matched_toks:
                    ratio = len(matched_toks) / len(tokens)
                    credit = 1.0 if ratio >= 0.8 else 0.5
                    status = "matched" if credit == 1.0 else "partial"
                    quote = ", ".join(matched_toks)
                else:
                    credit = 0.0
                    status = "missing"
                    quote = None

            matches.append({
                "requirement_name": name,
                "category": cat_enum.value,
                "importance": imp_enum.value,
                "credit": credit,
                "status": status,
                "evidence_quote": quote
            })

        scoring = calculate_open_domain_weighted_score(requirements, matches)

        skill_gaps = [m["requirement_name"] for m in matches if m["credit"] < 0.5]
        strengths = [m["requirement_name"] for m in matches if m["credit"] >= 0.5]

        parsed_reqs = [
            ExtractedRequirement(
                name=r["name"],
                category=_safe_category(r.get("category", "skill")),
                importance=_safe_importance(r.get("importance", "must_have")),
                weight=IMPORTANCE_WEIGHTS.get(_safe_importance(r.get("importance", "must_have")), 1.0),
                raw_text=r.get("raw_text")
            )
            for r in requirements
        ]

        parsed_matches = [
            CandidateRequirementMatch(
                requirement_name=m["requirement_name"],
                category=_safe_category(m.get("category", "skill")),
                importance=_safe_importance(m.get("importance", "must_have")),
                weight=IMPORTANCE_WEIGHTS.get(_safe_importance(m.get("importance", "must_have")), 1.0),
                credit=m["credit"],
                evidence_quote=m.get("evidence_quote"),
                status=m["status"]
            )
            for m in matches
        ]

        return OpenDomainAnalysisResult(
            requirements=parsed_reqs,
            matches=parsed_matches,
            weighted_score=scoring["weighted_score"],
            category_breakdown=scoring["category_breakdown"],
            skill_gaps=skill_gaps,
            strengths=strengths
        )
