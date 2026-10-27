"""Long-term career guidance based on resume analysis."""
from typing import Dict, Any
from app.ai.client import GenAIClient
from app.prompts.career_prompt import CAREER_ADVICE_PROMPT
from app.utils.logger import logger

class CareerAdvisor:
    """Provide long-term career guidance."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
        self.is_fallback = False
    
    async def get_advice(
        self,
        resume: str,
        experience: str,
        goals: str,
        skill_gaps: list
    ) -> Dict[str, Any]:
        """Generate career advice."""
        try:
            self.is_fallback = False
            prompt = CAREER_ADVICE_PROMPT.format(
                resume=resume[:2000],
                experience=experience[:500] if experience else "Not specified",
                goals=goals[:500] if goals else "Career growth",
                skill_gaps=", ".join(skill_gaps[:5])
            )
            
            schema = {
                "advice": {
                    "short_term_goals": ["string"],
                    "long_term_goals": ["string"],
                    "skills_to_develop": [
                        {"skill": "string", "priority": "high|medium|low", "resources": ["string"]}
                    ],
                    "career_paths": [
                        {"title": "string", "description": "string", "timeline": "string"}
                    ],
                    "recommended_roles": ["string"],
                    "salary_expectations": {"range": "string", "factors": ["string"]}
                }
            }
            
            result = await self.client.generate_structured_content(prompt, schema)
            logger.info("Career advice generated")
            return result.get("advice", {})
            
        except Exception as e:
            logger.error(f"Career advice generation failed: {e}")
            self.is_fallback = True
            return self._get_default_advice(skill_gaps)
    
    def _get_default_advice(self, skill_gaps: list) -> Dict[str, Any]:
        """Get default advice if AI fails."""
        primary_skill = skill_gaps[0] if skill_gaps else "Identified Core Competencies"
        return {
            "short_term_goals": [
                f"Master {primary_skill}",
                "Build demonstrable work samples or case studies"
            ],
            "long_term_goals": [
                "Advance to senior practitioner or leadership role",
                "Expand professional network and domain expertise"
            ],
            "skills_to_develop": [
                {"skill": gap, "priority": "high", "resources": []}
                for gap in skill_gaps[:3]
            ],
            "career_paths": [
                {"title": "Senior Specialist", "description": "Lead complex domain initiatives and mentoring", "timeline": "2-3 years"},
                {"title": "Practice / Team Lead", "description": "Manage cross-functional teams and operational delivery", "timeline": "3-5 years"}
            ],
            "recommended_roles": ["Senior Associate", "Domain Specialist", "Practice Lead"],
            "salary_expectations": {"range": "Competitive industry standard", "factors": ["Experience", "Location", "Specialized Skills"]}
        }
