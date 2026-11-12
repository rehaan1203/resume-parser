"""Open-domain requirement and scoring models (D4 Specification)."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RequirementCategory(str, Enum):
    SKILL = "skill"
    DOMAIN_EXPERIENCE = "domain_experience"
    CREDENTIAL = "credential"
    EDUCATION = "education"
    LEADERSHIP = "leadership"
    TOOL = "tool"

class ImportanceTier(str, Enum):
    MUST_HAVE = "must_have"
    PREFERRED = "preferred"
    BONUS = "bonus"

IMPORTANCE_WEIGHTS: Dict[ImportanceTier, float] = {
    ImportanceTier.MUST_HAVE: 1.0,
    ImportanceTier.PREFERRED: 0.5,
    ImportanceTier.BONUS: 0.25,
}

class ExtractedRequirement(BaseModel):
    name: str = Field(..., description="Canonical requirement name or description")
    category: RequirementCategory = Field(default=RequirementCategory.SKILL)
    importance: ImportanceTier = Field(default=ImportanceTier.MUST_HAVE)
    weight: float = Field(default=1.0)
    raw_text: Optional[str] = None
    min_years: Optional[float] = None

class CandidateRequirementMatch(BaseModel):
    requirement_name: str
    category: RequirementCategory
    importance: ImportanceTier
    weight: float
    credit: float = Field(default=0.0, ge=0.0, le=1.0, description="1.0 for match, 0.5 partial, 0.0 missing")
    evidence_quote: Optional[str] = None
    candidate_source: Optional[str] = None
    status: str = Field(default="missing", description="matched | partial | missing")

class OpenDomainAnalysisResult(BaseModel):
    requirements: List[ExtractedRequirement] = []
    matches: List[CandidateRequirementMatch] = []
    weighted_score: float = Field(..., ge=0.0, le=100.0)
    category_breakdown: Dict[str, Dict[str, Any]] = {}
    skill_gaps: List[str] = []
    strengths: List[str] = []

