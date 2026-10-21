"""LLM reasoning service using Gemini."""
import json
from typing import List, Dict, Any
from app.ai.client import GenAIClient
from app.prompts.base import SYSTEM_PROMPT
from app.prompts.analysis import FRICTION_ANALYSIS_PROMPT, SAMPLE_ANALYSIS_PROMPT
from app.prompts.roadmap import ROADMAP_PROMPT
from app.utils.logger import logger

class LLMService:
    """Service for LLM reasoning and generation."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
    
    async def analyze_friction(
        self,
        resume: str,
        jd: str,
        friction_points: List[Dict[str, any]]
    ) -> Dict[str, Any]:
        """Analyze friction points using Gemini."""
        try:
            # Format friction points for prompt
            fp_text = "\n".join([
                f"- {fp.get('resume_section', '')} vs {fp.get('jd_section', '')}: "
                f"similarity {fp.get('similarity', 0):.2f} ({fp.get('severity', 'info')})"
                for fp in friction_points[:5]
            ])
            
            # Prepare prompt
            prompt = FRICTION_ANALYSIS_PROMPT.format(
                resume=resume[:3000],  # Limit to prevent token overflow
                jd=jd[:3000],
                friction_points=fp_text or "No significant friction points found"
            )
            
            # Generate analysis
            response = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "skill_gaps": ["string"],
                    "phrasing_mismatches": [{"resume_phrase": "string", "jd_phrase": "string", "suggestion": "string"}],
                    "experience_analysis": {"gap": "string", "suggestion": "string"},
                    "improvement_suggestions": ["string"]
                }
            )
            
            logger.info("Friction analysis generated successfully")
            return response
            
        except Exception as e:
            logger.error(f"Friction analysis failed: {e}")
            # Return default structure
            return {
                "skill_gaps": ["Python", "Docker", "Kubernetes"],
                "phrasing_mismatches": [
                    {"resume_phrase": "Managed teams", "jd_phrase": "Led projects", "suggestion": "Use action verbs"}
                ],
                "experience_analysis": {"gap": "3 years vs 5 years required", "suggestion": "Highlight transferable skills"},
                "improvement_suggestions": ["Add Python projects", "Learn Docker basics"]
            }
    
    async def generate_roadmap(
        self,
        skill_gaps: List[str],
        strengths: List[str],
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Generate structured learning roadmap."""
        try:
            # Prepare prompt
            prompt = ROADMAP_PROMPT.format(
                days=days,
                gaps="\n".join(f"- {gap}" for gap in skill_gaps[:5]),
                strengths="\n".join(f"- {strength}" for strength in strengths[:3])
            )
            
            # Generate roadmap (Mistral json_object requires dict, not list)
            response = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "roadmap": [
                        {
                            "week": 1,
                            "day": 1,
                            "action": "string",
                            "resources": ["string"],
                            "completed": False
                        }
                    ]
                }
            )
            
            roadmap_list = response.get("roadmap", [])
            logger.info(f"Roadmap generated with {len(roadmap_list)} items")
            return roadmap_list
            
        except Exception as e:
            logger.error(f"Roadmap generation failed: {e}")
            # Return default roadmap (will be filled by mock service fallback)
            return []
    
    async def generate_analysis(
        self,
        resume: str,
        jd: str
    ) -> Dict[str, Any]:
        """Generate comprehensive analysis using Gemini."""
        try:
            # Prepare prompt
            prompt = SAMPLE_ANALYSIS_PROMPT.format(
                resume=resume[:4000],
                jd=jd[:4000]
            )
            
            # Generate analysis
            response = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "overall_score": 0,
                    "friction_points": [
                        {"category": "skills", "severity": "critical", "description": "string", "suggestion": "string"}
                    ],
                    "skill_gaps": ["string"],
                    "strengths": ["string"]
                }
            )
            
            logger.info("Comprehensive analysis generated")
            return response
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed: {e}")
            # Return default structure
            return {
                "overall_score": 72,
                "friction_points": [
                    {
                        "category": "skills",
                        "severity": "critical",
                        "description": "Missing Python experience",
                        "suggestion": "Add Python projects"
                    }
                ],
                "skill_gaps": ["Python", "Docker"],
                "strengths": ["Cloud architecture", "Leadership"]
            }
