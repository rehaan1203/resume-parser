"""Unified API Models."""
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    resume: str = Field(..., description="The candidate's resume text", min_length=50)
    jd_text: Optional[str] = Field(None, description="The job description text", alias="jdText")
    jd_url: Optional[str] = Field(None, description="URL to extract the job description from", alias="jdUrl")
    experience: Optional[str] = Field(None, description="Candidate's experience summary")
    career_goals: Optional[str] = Field(None, description="Candidate's career goals")
    include_roadmap: bool = Field(True, description="Include 30-day roadmap in response", alias="includeRoadmap")
    
    @model_validator(mode='after')
    def validate_jd_input(self):
        """Ensure at least one JD input is provided."""
        if not self.jd_url and not self.jd_text:
            raise ValueError("Either jd_text or jd_url must be provided")
        return self
    
    @field_validator('jd_url')
    @classmethod
    def validate_url(cls, v):
        """Validate URL format if provided."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v

class TransitionRequest(BaseModel):
    resume: str = Field(..., description="The candidate's resume text")
    jd: str = Field(..., description="The job description text")
    resume_domain: str = Field(..., description="The candidate's domain")
    jd_domain: str = Field(..., description="The required domain")

class FrictionPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., description="Unique identifier")
    category: str
    severity: Literal['critical', 'warning', 'info']
    description: str
    suggestion: str
    related_to: Optional[str] = Field(None, alias="relatedTo")

class RoadmapItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    week: int = Field(..., ge=1)
    day: int = Field(..., ge=1)
    action: str
    resources: List[str] = Field(default_factory=list)
    completed: bool = False

class AnalysisResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat()}
    )
    id: Optional[str] = Field(None, description="Unique analysis ID")
    overall_score: Optional[int] = Field(None, ge=0, le=100, alias="overallScore")
    skills_detected: Optional[int] = Field(None, alias="skillsDetected")
    low_confidence: Optional[bool] = Field(None, alias="lowConfidence")
    friction_points: List[Dict[str, Any]] = Field(default_factory=list, alias="frictionPoints")
    skill_gaps: List[str] = Field(default_factory=list, alias="skillGaps")
    strengths: List[str] = Field(default_factory=list)
    roadmap: Any = Field(None)
    timestamp: Optional[datetime] = None
    
    # Domain Mismatch fields
    status: Optional[str] = None
    message: Optional[str] = None
    resume_domain: Optional[str] = None
    jd_domain: Optional[str] = None
    transition_available: Optional[bool] = None
    
    # New fields for 4-Phase deterministic pipeline
    executive_summary: Optional[str] = Field(None, alias="executiveSummary")
    score_breakdown: Optional[Dict[str, int]] = Field(None, alias="scoreBreakdown")
    ats_optimization: Optional[Dict[str, Any]] = Field(None, alias="atsOptimization")
    domain_analysis: Optional[Dict[str, Any]] = Field(None, alias="domainAnalysis")
    skill_analysis: Optional[Dict[str, Any]] = Field(None, alias="skillAnalysis")
    seniority_analysis: Optional[Dict[str, Any]] = Field(None, alias="seniorityAnalysis")
    cross_validation_status: Optional[Dict[str, Any]] = Field(None, alias="crossValidationStatus")
    perfect_match: Optional[bool] = Field(None, alias="perfectMatch")
    
    # Legacy fields
    gap_strategies: Optional[List[dict]] = Field(None, alias="gapStrategies")
    processing_time_ms: Optional[int] = Field(None, alias="processingTimeMs")
    ai_metadata: Optional[dict] = Field(None, alias="aiMetadata")
    reasoning: Optional[str] = None
    resources: Optional[dict] = Field(None, description="Courses and videos")
    iteration_metadata: Optional[dict] = Field(None)
    planning_metadata: Optional[dict] = Field(None)
    analysis_type: Optional[str] = Field(None)
    learned_patterns_applied: Optional[int] = Field(0)
    agent_outputs: Optional[Dict[str, Any]] = Field(None)
    critic_quality_score: Optional[int] = Field(None)
    ats_optimization_tips: Optional[List[dict]] = Field(None, alias="atsOptimizationTips")
    seniority_alignment: Optional[dict] = Field(None, alias="seniorityAlignment")
    conditional_sections: Optional[dict] = Field(None, alias="conditionalSections")

class CacheStatsResponse(BaseModel):
    stats: Dict[str, float]
    size: int
    enabled: bool
    redis_available: bool

class CacheClearResponse(BaseModel):
    message: str

class CacheWarmupResponse(BaseModel):
    warmed_entries: int

class CacheInvalidateResponse(BaseModel):
    message: str

class CacheKeysResponse(BaseModel):
    keys: List[str]
    total: int
    limited: bool

