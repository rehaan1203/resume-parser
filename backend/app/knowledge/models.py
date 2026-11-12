"""Pydantic schemas for the RAG Knowledge Base."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

class ResourceType(str, Enum):
    COURSE = "course"
    YOUTUBE_VIDEO = "youtube_video"
    CERTIFICATION = "certification"
    DOCUMENTATION = "documentation"

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class VideoChapter(BaseModel):
    timestamp_seconds: int = Field(..., description="Start offset in seconds")
    title: str = Field(..., description="Chapter topic or module name")
    url_anchor: str = Field(..., description="URL parameter e.g. 't=14m20s'")

class ChildChunk(BaseModel):
    id: str = Field(..., description="Unique chunk slug identifier")
    title: str = Field(..., description="Chunk or sub-topic title")
    content: str = Field(..., description="Granular syllabus text or statutory excerpt (~100 tokens)")
    skills_covered: List[str] = Field(default_factory=list, description="Specific skills in this chunk")
    parent_id: Optional[str] = Field(None, description="Parent VerifiedResource id")

class VerifiedResource(BaseModel):
    id: str = Field(..., description="Unique slug identifier (e.g. tech-fastapi-course)")
    title: str = Field(..., description="Canonical course/video/certification title")
    url: str = Field(..., description="Verified direct URL")
    platform: str = Field(..., description="Platform name (e.g., Coursera, YouTube, AWS, edX, MIT OCW)")
    type: ResourceType = Field(default=ResourceType.COURSE)
    domain: str = Field(..., description="Primary domain (e.g. tech, healthcare, trades, legal, finance)")
    jurisdiction: str = Field(default="GLOBAL", description="Legal/regulatory jurisdiction: 'GLOBAL', 'IN', 'US', 'EU', 'UK'")
    skills_covered: List[str] = Field(default_factory=list, description="List of discrete skills covered")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.BEGINNER)
    duration_hours: Optional[float] = Field(None, description="Estimated duration in hours")
    is_free: bool = Field(default=True, description="True if freely accessible without paywall")
    verified_at: str = Field(default="2026-10-29", description="Date verified active (ISO)")
    health_status: str = Field(default="active", description="active, degraded, or broken")
    last_checked_at: Optional[str] = Field(None, description="Timestamp of last health verification")
    description: str = Field(..., description="Syllabus overview or video description for semantic matching")
    publication_year: Optional[int] = Field(default=2024, description="Year of publication/major revision")
    chapters: List[VideoChapter] = Field(default_factory=list, description="Timestamped video chapters")
    child_chunks: List[ChildChunk] = Field(default_factory=list, description="Granular sub-topic chunks for hierarchical retrieval")
    active_timestamp_url: Optional[str] = Field(default=None, description="URL with deep-linked timestamp anchor")
    matched_chapter: Optional[str] = Field(default=None, description="Title of specific matched video chapter")

class ResourceSearchResult(BaseModel):
    resource: VerifiedResource
    score: float = Field(..., ge=0.0, le=1.0, description="Hybrid relevance score")
    matched_skills: List[str] = Field(default_factory=list)


class PhrasingTemplate(BaseModel):
    id: str = Field(..., description="Unique phrasing template id")
    domain: str = Field(..., description="Primary domain")
    skills: List[str] = Field(default_factory=list, description="Associated skills")
    action_verbs: List[str] = Field(default_factory=list, description="Proven strong action verbs")
    star_template: str = Field(..., description="STAR framework bullet template")
    example_before: str = Field(..., description="Weak before bullet")
    example_after: str = Field(..., description="Strong metric-driven after bullet")


class TransitionBridge(BaseModel):
    id: str = Field(..., description="Unique slug for bridge (e.g. healthcare-to-tech)")
    source_domain: str = Field(..., description="Source background domain")
    target_domain: str = Field(..., description="Target role domain")
    transferable_strengths: List[str] = Field(default_factory=list, description="Directly transferable core strengths")
    bridge_certifications: List[str] = Field(default_factory=list, description="Standard bridge credentials")
    strategic_advice: str = Field(..., description="Actionable repositioning strategy for resume/interview")
    recommended_projects: List[str] = Field(default_factory=list, description="Portfolio project ideas demonstrating crossover capability")


class StarModelAnswer(BaseModel):
    situation: str = Field(..., description="Context and challenge")
    task: str = Field(..., description="Candidate responsibility")
    action: str = Field(..., description="Specific high-leverage execution")
    result: str = Field(..., description="Quantified business outcome")


class InterviewGuideItem(BaseModel):
    id: str = Field(..., description="Unique interview guide id")
    domain: str = Field(..., description="Domain category")
    skill_focus: str = Field(..., description="Target skill or competency")
    question_type: str = Field(default="behavioral", description="behavioral, technical, or situational")
    question: str = Field(..., description="The interview question")
    evaluation_criteria: List[str] = Field(default_factory=list, description="Hiring rubric: what great answers demonstrate")
    star_model_answer: StarModelAnswer = Field(..., description="Exemplar STAR answer")


class SkillNode(BaseModel):
    id: str = Field(..., description="Unique skill node id (e.g. kubernetes, dcf_modeling)")
    name: str = Field(..., description="Human readable skill display name")
    domain: str = Field(..., description="Primary domain: tech, finance, healthcare, legal, trades")
    difficulty_tier: str = Field(default="intermediate", description="beginner, intermediate, advanced, master")
    prerequisites: List[str] = Field(default_factory=list, description="List of skill IDs that must be mastered before this skill")
    description: str = Field(..., description="Brief syllabus/competency description")


class PrerequisiteChainResult(BaseModel):
    target_skill: str
    unfulfilled_prerequisites: List[SkillNode] = Field(default_factory=list)
    pedagogical_order: List[str] = Field(default_factory=list)


class HyDEQuery(BaseModel):
    skill: str
    domain: str
    hypothetical_curriculum: str
    is_fallback: bool = False


class CRAGGrade(BaseModel):
    resource_id: str
    grade: str = Field(..., description="correct, ambiguous, or incorrect")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class QueryConstraints(BaseModel):
    max_duration_hours: Optional[float] = Field(None, description="Maximum course duration in hours")
    is_free: Optional[bool] = Field(None, description="Require free or paid")
    required_platforms: List[str] = Field(default_factory=list, description="Specific platforms required")
    allowed_types: List[str] = Field(default_factory=list, description="course, youtube_video, certification, documentation")
    max_difficulty: Optional[str] = Field(None, description="beginner, intermediate, advanced")
    target_jurisdiction: Optional[str] = Field(None, description="Target regulatory jurisdiction (IN, US, EU, UK, GLOBAL)")
    excluded_skills: List[str] = Field(default_factory=list, description="Excluded skills / anti-skills (e.g. ['aws', 'django'])")
    excluded_jurisdictions: List[str] = Field(default_factory=list, description="Excluded jurisdictions (e.g. ['us'])")
    excluded_platforms: List[str] = Field(default_factory=list, description="Excluded platforms (e.g. ['udemy'])")


class RAGASTriadResult(BaseModel):
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Score of retrieved context relevance to query")
    faithfulness: float = Field(..., ge=0.0, le=1.0, description="Groundedness: extent to which output is supported by context")
    answer_relevance: float = Field(..., ge=0.0, le=1.0, description="Score of answer relevance to target transition")
    is_grounded: bool = Field(default=True, description="True if passes faithfulness threshold (>= 0.80)")
    reasoning: str = Field(default="", description="Detailed triad evaluation rationale")


class DiagramResource(BaseModel):
    id: str = Field(..., description="Unique diagram slug (e.g. diag-k8s-architecture)")
    domain: str = Field(..., description="tech, finance, healthcare, legal, trades")
    associated_skills: List[str] = Field(default_factory=list, description="Skills this diagram illustrates")
    title: str = Field(..., description="Human readable diagram title")
    description: str = Field(..., description="What the diagram explains")
    mermaid_definition: str = Field(..., description="Executable Mermaid diagram code block")



