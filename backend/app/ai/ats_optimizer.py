"""ATS optimization suggestions for resumes."""
from typing import List, Dict, Any
from app.ai.client import GenAIClient
from app.prompts.ats_prompt import ATS_OPTIMIZATION_PROMPT
from app.utils.document_chunker import extract_core_sections
from app.utils.logger import logger

class ATSOptimizer:
    """Optimize resume for ATS systems."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
        self.is_fallback = False
    
    async def optimize(
        self,
        resume: str,
        jd: str,
        friction_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate ATS optimization suggestions."""
        try:
            self.is_fallback = False
            # Prepare friction points for prompt
            fp_text = "\n".join([
                f"- {fp.get('description', '')}: {fp.get('suggestion', '')}"
                for fp in friction_points[:3]
            ])
            
            prompt = ATS_OPTIMIZATION_PROMPT.format(
                resume=extract_core_sections(resume, doc_type="resume", max_chars=4000),
                jd=extract_core_sections(jd, doc_type="jd", max_chars=4000),
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
            self.is_fallback = True
            return self._get_default_suggestions()
    
    def _get_default_suggestions(self) -> Dict[str, Any]:
        """Get default suggestions if AI fails."""
        return {
            "keywords_to_add": ["Relevant Industry Certifications", "Core Domain Methodologies", "Standard Regulatory Frameworks"],
            "phrasing_improvements": [
                {"original": "Managed responsibilities", "suggested": "Orchestrated key initiatives", "reason": "More impactful and demonstrates leadership"},
                {"original": "Assisted with tasks", "suggested": "Executed core operational deliverables", "reason": "Demonstrates proactive ownership"}
            ],
            "section_reordering": ["Core Competencies", "Professional Experience", "Education & Certifications"],
            "formatting_tips": ["Use standard section headings", "Include measurable outcomes", "Use clear, consistent bullet points"],
            "ats_score": 65
        }
