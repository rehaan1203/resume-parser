"""Long-term career guidance based on resume analysis."""
from typing import Dict, Any
from app.ai.client import GenAIClient
from app.prompts.career import CAREER_ADVICE_PROMPT
from app.utils.logger import logger

class CareerAdvisor:
    """Provide long-term career guidance."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
    
    async def get_advice(
        self,
        resume: str,
        experience: str,
        goals: str,
        skill_gaps: list
    ) -> Dict[str, Any]:
        """Generate career advice."""
        try:
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
            return self._get_default_advice(skill_gaps)
    
    def _get_default_advice(self, skill_gaps: list) -> Dict[str, Any]:
        """Get default advice if AI fails."""
        return {
            "short_term_goals": [
                f"Learn {skill_gaps[0] if skill_gaps else 'Python'}",
                "Build a portfolio project"
            ],
            "long_term_goals": [
                "Achieve senior/lead role",
                "Build industry network"
            ],
            "skills_to_develop": [
                {"skill": gap, "priority": "high", "resources": ["https://example.com"]}
                for gap in skill_gaps[:3]
            ],
            "career_paths": [
                {"title": "Senior Developer", "description": "Lead technical projects", "timeline": "2-3 years"},
                {"title": "Team Lead", "description": "Manage and mentor team", "timeline": "3-5 years"}
            ],
            "recommended_roles": ["Software Engineer", "Technical Lead"],
            "salary_expectations": {"range": "$80k-$120k", "factors": ["Experience", "Location", "Skills"]}
        }
