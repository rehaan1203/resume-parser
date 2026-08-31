"""Unified Domain Models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Literal, Union, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class InterviewQuestion(BaseModel):
    category: str = Field(..., description="technical|behavioral|situational")
    question: str
    expected_answer: str
    hint: str
    difficulty: str = Field(..., description="easy|medium|hard")

class InterviewQuestionsResponse(BaseModel):
    questions: List[InterviewQuestion]
    total: int
    metadata: Dict[str, Any]

class PhrasingImprovement(BaseModel):
    original: str
    suggested: str
    reason: str

class ATSSuggestions(BaseModel):
    keywords_to_add: List[str]
    phrasing_improvements: List[PhrasingImprovement]
    section_reordering: List[str]
    formatting_tips: List[str]
    ats_score: int

class ATSOptimizationResponse(BaseModel):
    suggestions: ATSSuggestions
    metadata: Dict[str, Any]

class SkillToDevelop(BaseModel):
    skill: str
    priority: str
    resources: List[str]

class CareerPath(BaseModel):
    title: str
    description: str
    timeline: str

class SalaryExpectations(BaseModel):
    range: str
    factors: List[str]

class CareerAdvice(BaseModel):
    short_term_goals: List[str]
    long_term_goals: List[str]
    skills_to_develop: List[SkillToDevelop]
    career_paths: List[CareerPath]
    recommended_roles: List[str]
    salary_expectations: SalaryExpectations

class CareerAdviceResponse(BaseModel):
    advice: CareerAdvice
    metadata: Dict[str, Any]

class WriterOutputSchema(BaseModel):
    resume_domain: str = Field(..., description="The domain or industry identified from the resume")
    jd_domain: str = Field(..., description="The domain or industry identified from the job description")
    domain_match: bool = Field(..., description="True if domains match or are highly related, False otherwise")
    overall_score: int = Field(..., ge=0, le=100, description="Overall match score between 0 and 100")
    friction_points: List[Any] = Field(default_factory=list, description="List of identified friction points")
    skill_gaps: List[str] = Field(default_factory=list, description="List of skills missing from the resume")
    strengths: List[str] = Field(default_factory=list, description="List of strong matching skills/experiences")
    reasoning: str = Field(..., description="Brief explanation of the score and match")

class SpecificIssue(BaseModel):
    issue: str = Field(..., description="Description of the flaw found in the original analysis")
    suggested_fix: str = Field(..., description="Suggested correction for the issue")

class RevisedAnalysis(BaseModel):
    friction_points: List[Any] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = Field(None, description="Revised reasoning if any")

class CriticOutputSchema(BaseModel):
    critique_found: bool = Field(..., description="True if flaws were found in the original analysis")
    specific_issues: List[SpecificIssue] = Field(default_factory=list, description="List of specific flaws found")
    revised_score: int = Field(..., ge=0, le=100, description="Revised score after critique")
    revised_analysis: RevisedAnalysis = Field(..., description="The corrected analysis data")

class Roadmap30DayData(BaseModel):
    type: Literal["30_day"]
    total_days: int
    weeks: List[Dict[str, Any]]

class Roadmap90DayData(BaseModel):
    type: Literal["90_day"]
    total_days: int
    months: List[Dict[str, Any]]

class RoadmapTransitionData(BaseModel):
    type: Literal["transition"]
    total_months: int
    phases: List[Dict[str, Any]]
    alternative_roles: List[str]

class UnifiedRoadmapResult(BaseModel):
    type: str
    title: str
    estimated_timeline: str
    ai_note: Optional[str] = None
    data: Union[Roadmap30DayData, Roadmap90DayData, RoadmapTransitionData, Dict[str, Any]]

class ATSAdvancedData(BaseModel):
    type: Literal["advanced"]
    keywords: List[str]
    phrasing: List[str]
    formatting_tips: List[str]

class ATSPartialData(BaseModel):
    type: Literal["partial"]
    relevant_skills: List[str]
    transferable_skills: List[str]
    keywords: List[str]
    additional_tips: List[str]

class ATSTransitionData(BaseModel):
    type: Literal["transition"]
    education: List[str]
    portfolio: List[str]
    certifications: List[str]
    resume_strategy: List[str]
    alternative_roles: List[str]

class UnifiedATSResult(BaseModel):
    type: str
    title: str
    data: Union[ATSAdvancedData, ATSPartialData, ATSTransitionData, Dict[str, Any]]

class SeniorityComparisonData(BaseModel):
    type: Literal["comparison"]
    your_level: str
    required_level: str
    alignment: str
    recommendation: List[str]

class SeniorityGapAnalysisData(BaseModel):
    type: Literal["gap_analysis"]
    experience_gap: str
    recommendation: List[str]
    target_level: str

class SeniorityCareerGapData(BaseModel):
    type: Literal["career_gap"]
    domain_mismatch: str
    timeline: str
    recommendation: List[str]
    alternative_roles: List[str]

class UnifiedSeniorityResult(BaseModel):
    type: str
    title: str
    data: Union[SeniorityComparisonData, SeniorityGapAnalysisData, SeniorityCareerGapData, Dict[str, Any]]

class ConditionalSections(BaseModel):
    roadmap: UnifiedRoadmapResult
    ats_optimization: UnifiedATSResult
    seniority_alignment: UnifiedSeniorityResult

class Domain(str, Enum):
    LEGAL = "legal"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    ARCHITECTURE = "architecture"
    EDUCATION = "education"
    AI_ML = "ai_ml"
    SOFTWARE = "software"
    DESIGN = "design"
    MARKETING = "marketing"
    SALES = "sales"
    HR = "hr"
    OPERATIONS = "operations"
    ENGINEERING = "engineering"
    SCIENCE = "science"
    UNKNOWN = "unknown"

class DomainDetectionResult(BaseModel):
    domain: Domain
    confidence: int = Field(..., ge=0, le=100)
    evidence: List[str]
    reasoning: str

class DomainResource(BaseModel):
    name: str
    platform: str
    url: str
    type: str = Field(..., description="free_course|paid_course|youtube_channel|certification|paper")
    description: Optional[str] = None

class DomainResources(BaseModel):
    free_courses: List[DomainResource] = []
    paid_courses: List[DomainResource] = []
    youtube_channels: List[DomainResource] = []
    certifications: List[DomainResource] = []
    papers: List[DomainResource] = []

class GapAnalysisResult(BaseModel):
    resume_domain: Domain
    jd_domain: Domain
    is_same_domain: bool
    is_related_domain: bool
    gap_type: str = Field(..., description="upskill|transition|career_change")
    match_score: int
    timeline: Dict[str, Any]
    reasoning: str

class TimelineResult(BaseModel):
    type: str = Field(..., description="mini_upskill|short_upskill|standard_upskill|extended_upskill|transition|career_change")
    duration: str
    days: Optional[int] = None
    weeks: Optional[int] = None
    months: Optional[int] = None
    description: str

class Feedback(BaseModel):
    analysis_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    correction: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    feedback_type: str = Field(..., description="explicit|implicit")

class Pattern(BaseModel):
    id: str
    type: str = Field(..., description="domain_mismatch|skill_inference|scoring_rule|...")
    context: Dict[str, Any]
    rule: str
    success_count: int = 0
    failure_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    confidence: float = Field(..., ge=0, le=1)
    version: int = 1
    deprecated: bool = False
    superseded_by: Optional[str] = None

class PatternMatch(BaseModel):
    pattern: Pattern
    relevance_score: float = Field(..., ge=0, le=1)
    context_overlap: List[str]

class LearningStats(BaseModel):
    total_patterns: int
    total_feedback: int
    average_rating: float
    pattern_success_rate: float
    top_patterns: List[Pattern]
    recent_feedback: List[Feedback]
    accuracy_trend: List[float]
    last_updated: datetime

class FeedbackRequest(BaseModel):
    analysis_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    corrections: Optional[Dict[str, Any]] = None
