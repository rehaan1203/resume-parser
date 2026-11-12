"""Jurisdiction & Geo-Aware Multi-Domain RAG Router.

Enforces geographical and regulatory routing across ALL domains:
- Legal: DPDP Act 2023 / IT Act 2000 / Companies Act (IN) vs USPTO / FRCP (US) vs GDPR (EU)
- Finance: SEBI / RBI / Ind AS / GST (IN) vs SEC EDGAR / US GAAP (US) vs MiFID II / IFRS (EU)
- Healthcare: ABDM / NABH / Biomedical Waste (IN) vs HIPAA / NCLEX / FDA (US) vs NHS (UK)
- Trades: BIS IS 732 / IS 3043 / CEA 230V 50Hz (IN) vs NEC NFPA 70 120V / OSHA (US) vs BS 7671 (UK)
- Tech: NPCI UPI / ONDC / CERT-In (IN) vs Sovereign Cloud / Universal Tech (GLOBAL)
"""
import re
from typing import List, Optional, Tuple, Dict, Set
from app.knowledge.models import VerifiedResource, ResourceSearchResult
from app.utils.logger import logger

# Multi-domain jurisdiction indicators mapping keywords to specific territories
JURISDICTION_INDICATORS: Dict[str, List[str]] = {
    "IN": [
        # Country & General
        "india", "indian",
        # Legal & Compliance
        "dpdp", "dpdp act", "it act 2000", "it act", "section 43a", "cert-in",
        "companies act 2013", "companies act", "mca", "roc", "aibe", "bar council of india",
        "bci", "bns", "bnss", "cpc 1908", "indian contract act",
        # Finance & Banking
        "sebi", "rbi", "fema", "nbfc", "ind as", "indian gaap", "icai", "gst",
        "income tax act 1961", "income tax act", "lodr", "rbi master directions",
        # Healthcare
        "abdm", "nha", "ayushman bharat", "abha", "nabh", "clinical establishments act",
        "biomedical waste rules", "nmc", "inc",
        # Trades & Building Codes
        "bis", "is 732", "is 3043", "national building code india", "nbc 2016",
        "cea regulations", "central electricity authority", "dgfasli", "factories act 1948",
        # Tech & Digital Infrastructure
        "upi", "npci", "ondc", "beckn", "aadhaar ekyc"
    ],
    "US": [
        # Country & General
        "united states", "usa", "u.s.", "u.s.a.",
        # Legal & Compliance
        "uspto", "frcp", "delaware corporate", "dgcl", "fcpa",
        # Finance & Securities
        "sec", "edgar", "us gaap", "finra", "sox", "sarbanes oxley", "10-k", "10-q",
        # Healthcare & Nursing
        "hipaa", "hitech", "fda", "nclex", "nclex-rn", "aha bls", "cdc infection control",
        # Trades & Physical Safety
        "nec", "nfpa", "nfpa 70", "epa 608", "osha", "asme", "aws welding"
    ],
    "EU": [
        # Region & General
        "european union", "eu", "europe",
        # Legal, Tech, Data
        "gdpr", "eu ai act", "dora", "iapp gdpr",
        # Finance & Healthcare
        "mifid", "ifrs", "mdr", "ema"
    ],
    "UK": [
        # Country & General
        "united kingdom", "uk", "british",
        # Legal, Finance, Healthcare, Trades
        "fca", "pra", "english common law", "nhs", "bs 7671", "iee wiring"
    ]
}

# Domains where regional regulatory/statutory frameworks strictly diverge
TERRITORIAL_DOMAINS: Set[str] = {
    "legal",
    "compliance",
    "finance",
    "healthcare",
    "trades"
}

class GeoRouter:
    """Routes and filters learning resources based on geographical & regulatory jurisdiction across all domains."""

    def __init__(self):
        pass

    def detect_jurisdiction(self, query: str, explicit_jurisdiction: Optional[str] = None) -> str:
        """
        Infer regulatory jurisdiction from explicit user setting or query keywords across all domains.
        Defaults to 'GLOBAL' if no specific territory is detected.
        """
        if explicit_jurisdiction:
            clean_exp = explicit_jurisdiction.strip().upper()
            if clean_exp in ("IN", "INDIA"):
                return "IN"
            if clean_exp in ("US", "USA", "UNITED STATES"):
                return "US"
            if clean_exp in ("EU", "EUROPE"):
                return "EU"
            if clean_exp in ("UK", "UNITED KINGDOM"):
                return "UK"
            return clean_exp

        text = query.lower()
        # Scan indicators with token boundary matching
        for j_code, indicators in JURISDICTION_INDICATORS.items():
            for ind in indicators:
                if re.search(r"\b" + re.escape(ind) + r"\b", text):
                    logger.debug(f"GeoRouter: detected jurisdiction '{j_code}' from indicator '{ind}'")
                    return j_code

        return "GLOBAL"

    def score_geo_compatibility(
        self,
        resource_jurisdiction: str,
        target_jurisdiction: str,
        domain: str = "general"
    ) -> float:
        """
        Calculate regulatory compatibility score S_geo(r, J_u) across ALL domains.
        Strict pruning (0.0) is applied whenever territorial statutory/technical codes clash
        (e.g., Indian electrician given US 120V NEC, Indian nurse given US NCLEX/HIPAA, Indian auditor given US SEC EDGAR).
        """
        r_jur = (resource_jurisdiction or "GLOBAL").strip().upper()
        t_jur = (target_jurisdiction or "GLOBAL").strip().upper()
        dom = (domain or "general").strip().lower()

        # If user has no specific territory or universal
        if t_jur == "GLOBAL":
            return 1.0

        if r_jur == t_jur:
            return 1.0

        # Universal global concepts (e.g., Python, Docker, general DCF modeling, general ECG interpretation)
        if r_jur == "GLOBAL":
            if dom in ("legal", "compliance"):
                return 0.40  # Generic law lacks statutory force
            elif dom in ("finance", "healthcare", "trades"):
                return 0.70  # Foundational theory applies, but local codes preferred
            else:
                return 0.90  # Tech, general engineering

        # Explicit territorial conflicts (e.g. US resource for Indian inquiry, or IN resource for US inquiry)
        if dom in TERRITORIAL_DOMAINS:
            # Hard territorial pruning across Legal, Finance, Healthcare, and Trades!
            logger.debug(f"GeoRouter: strict territorial pruning for {r_jur} vs target {t_jur} in domain '{dom}'")
            return 0.0

        # Tech domain: foreign technical frameworks (e.g. US cloud certs) remain accessible with mild damping (0.70)
        if dom == "tech":
            return 0.70

        return 0.50

    def filter_and_route(
        self,
        candidates: List[ResourceSearchResult],
        target_jurisdiction: str,
        domain: str = "general"
    ) -> List[ResourceSearchResult]:
        """Apply territorial compatibility scoring and filter strictly out-of-jurisdiction resources across all domains."""
        routed: List[ResourceSearchResult] = []
        t_jur = target_jurisdiction.strip().upper() if target_jurisdiction else "GLOBAL"

        for item in candidates:
            res = item.resource
            r_jur = getattr(res, "jurisdiction", "GLOBAL")
            geo_mult = self.score_geo_compatibility(r_jur, t_jur, domain=domain)
            
            # Drop zero-compatibility territorial conflicts
            if geo_mult <= 0.0:
                continue

            # Apply geo compatibility multiplier to score
            new_score = round(item.score * geo_mult, 4)
            routed.append(ResourceSearchResult(
                resource=res,
                score=min(1.0, new_score),
                matched_skills=item.matched_skills
            ))

        routed.sort(key=lambda x: x.score, reverse=True)
        return routed

_GLOBAL_GEO_ROUTER: Optional[GeoRouter] = None

def get_geo_router() -> GeoRouter:
    """Singleton getter for GeoRouter."""
    global _GLOBAL_GEO_ROUTER
    if _GLOBAL_GEO_ROUTER is None:
        _GLOBAL_GEO_ROUTER = GeoRouter()
    return _GLOBAL_GEO_ROUTER
