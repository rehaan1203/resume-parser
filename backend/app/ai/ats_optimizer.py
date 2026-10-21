"""ATS optimization suggestions for resumes."""
from typing import List, Dict, Any
from app.ai.client import GenAIClient
from app.prompts.ats_prompt import ATS_OPTIMIZATION_PROMPT
from app.utils.logger import logger

class ATSOptimizer:
    """Optimize resume for ATS systems."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
    
    async def optimize(
        self,
        resume: str,
        jd: str,
        friction_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate ATS optimization suggestions."""
        try:
            # Prepare friction points for prompt
            fp_text = "\n".join([
                f"- {fp.get('description', '')}: {fp.get('suggestion', '')}"
                for fp in friction_points[:3]
            ])
            
            prompt = ATS_OPTIMIZATION_PROMPT.format(
                resume=resume[:2000],
                jd=jd[:2000],
                friction_points=fp_text or "No friction points identified"
            )
            
            schema = {
                "suggestions": {
                    "keywords_to_add": ["string"],
                    "phrasing_improvements": [
                        {"original": "string", "suggested": "string", "reason": "string"}
                    ],
                    "section_reordering": ["string"],
                    "formatting_tips": ["string"],
                    "ats_score": 0
                }
            }
            
            result = await self.client.generate_structured_content(prompt, schema)
            logger.info("ATS optimization generated")
            return result.get("suggestions", {})
            
        except Exception as e:
            logger.error(f"ATS optimization failed: {e}")
            return self._get_default_suggestions()
    
    def _get_default_suggestions(self) -> Dict[str, Any]:
        """Get default suggestions if AI fails."""
        return {
            "keywords_to_add": ["Python", "Docker", "Kubernetes", "Cloud", "CI/CD"],
            "phrasing_improvements": [
                {"original": "Managed teams", "suggested": "Led teams", "reason": "More active and impactful"},
                {"original": "Worked on", "suggested": "Developed", "reason": "Shows ownership"}
            ],
            "section_reordering": ["Skills", "Experience", "Education"],
            "formatting_tips": ["Use bullet points", "Include metrics", "Use action verbs"],
            "ats_score": 65
        }
