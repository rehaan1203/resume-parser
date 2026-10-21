"""Phase 3 LLM Explainer - generates explanations based on fixed deterministic data."""
import asyncio
from typing import Dict, Any, List
from app.ai.client import GenAIClient
from app.utils.logger import logger
from app.prompts.analysis import build_executive_summary_prompt, build_mismatch_prompt
from app.prompts.ats import build_standard_ats_prompt, build_transition_ats_prompt
from app.prompts.roadmap import build_upskill_roadmap_prompt
from app.prompts.seniority import build_seniority_alignment_prompt

class Phase3Explainer:
    def __init__(self):
        self.client = GenAIClient()
        
    async def generate_executive_summary(self, score: int, strengths: List[str], gaps: List[str], seniority_gap: int) -> str:
        prompt = build_executive_summary_prompt(
            score=score,
            strengths=strengths,
            gaps=gaps,
            seniority_gap=seniority_gap
        )
        
        try:
            response = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={"summary": "string"}
            )
            return response.get("summary", "Summary could not be generated.")
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return f"Candidate achieved a {score}% match. Key strengths include {', '.join(strengths[:3])}. Focus on developing {', '.join(gaps[:3])}."

    async def generate_mismatch_message(self, resume_domain: str, jd_domain: str) -> str:
        prompt = build_mismatch_prompt(
            resume_domain=resume_domain,
            jd_domain=jd_domain
        )
        try:
            response = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={"message": "string"}
            )
            return response.get("message", f"Your experience is in {resume_domain}, but this role requires {jd_domain}.")
        except Exception as e:
            logger.error(f"Failed to generate mismatch message: {e}")
            return f"Your experience is in {resume_domain}, but this role requires {jd_domain}."

    async def generate_ats_optimization(self, gaps: List[str], jd_text: str, domain_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        is_mismatch = domain_analysis and domain_analysis.get("is_mismatch", False)
        if is_mismatch:
            resume_domain = domain_analysis.get("resume_domain", "").replace("_", " ").title()
            jd_domain = domain_analysis.get("jd_domain", "").replace("_", " ").title()
            prompt = build_transition_ats_prompt(
                resume_domain=resume_domain,
                jd_domain=jd_domain,
                gaps=gaps
            )
        else:
            prompt = build_standard_ats_prompt(gaps=gaps)
        
        try:
            return await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "keywords": ["string"],
                    "phrasing": [{"original": "string", "suggested": "string"}],
                    "formatting_tips": ["string"]
                }
            )
        except Exception as e:
            logger.error(f"Failed to generate ATS optimization: {e}")
            return {
                "keywords": [f"Add '{gap}' to Core Competencies" for gap in gaps[:3]],
                "phrasing": [],
                "formatting_tips": ["Use standard section headings", "Avoid tables and complex formatting"]
            }

    async def generate_roadmap(self, gaps: List[str], gap_type: str = "standard_upskill") -> Dict[str, Any]:
        """Generate a structured learning roadmap based on gap type."""
        
        weeks_count = 4
        if gap_type == "mini_upskill":
            weeks_count = 1
        elif gap_type == "short_upskill":
            weeks_count = 2
        elif gap_type == "extended_upskill":
            weeks_count = 8
        elif gap_type == "career_change":
            weeks_count = 12
            
        prompt = build_upskill_roadmap_prompt(gaps=gaps, gap_type=gap_type)
        
        try:
            return await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "type": "string",
                    "title": "string",
                    "weeks": [
                        {
                            "week": 0,
                            "focus": "string",
                            "days": [
                                {
                                    "day": 0,
                                    "action": "string",
                                    "resources": ["string"],
                                    "estimated_time": "string"
                                }
                            ]
                        }
                    ]
                }
            )
        except Exception as e:
            logger.error(f"Failed to generate roadmap: {e}")
            return {
                "type": gap_type,
                "title": f"Fallback Roadmap ({weeks_count} Weeks)",
                "weeks": []
            }

    async def generate_seniority_alignment(
        self,
        years_experience: int,
        required_years: int,
        your_level: str,
        required_level: str,
        gap: int,
        domain_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate detailed seniority alignment context and recommendations."""
        is_mismatch = domain_analysis and domain_analysis.get("is_mismatch", False)
        
        if is_mismatch:
            resume_domain = domain_analysis.get("resume_domain", "").replace("_", " ").title()
            jd_domain = domain_analysis.get("jd_domain", "").replace("_", " ").title()
            return {
                "your_level": "N/A",
                "your_years": years_experience,
                "required_level": required_level,
                "required_years": required_years,
                "gap": "Domain Mismatch",
                "alignment_status": "mismatch",
                "alignment_badge": "🔴 DOMAIN MISMATCH",
                "summary": f"Your experience is in {resume_domain}, but this role requires {jd_domain}. Seniority comparison is not applicable.",
                "recommendation": f"Consider roles in your domain ({resume_domain}) or pursue a complete career transition to {jd_domain}.",
                "next_steps": [
                    f"🎯 Identify roles that combine {resume_domain} and {jd_domain}",
                    f"📜 Pursue certifications in {jd_domain} if you want to transition",
                    f"📈 Network with professionals in both fields"
                ]
            }
        
        # Determine basic alignment status
        if gap <= 0:
            alignment_status = "match"
            badge = "✅ PERFECT MATCH"
        elif gap <= 2:
            alignment_status = "minor_gap"
            badge = "🟡 MINOR GAP"
        else:
            alignment_status = "significant_gap"
            badge = "🔴 SIGNIFICANT GAP"

        prompt = build_seniority_alignment_prompt(
            years_experience=years_experience,
            required_years=required_years,
            your_level=your_level,
            required_level=required_level,
            gap=gap,
            alignment_status=alignment_status
        )
        
        try:
            result = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "summary": "string",
                    "recommendation": "string",
                    "next_steps": ["string"]
                }
            )
            
            # Combine the LLM result with the deterministic data as requested
            return {
                "your_level": your_level,
                "your_years": years_experience,
                "required_level": required_level,
                "required_years": required_years,
                "gap": gap,
                "alignment_status": alignment_status,
                "alignment_badge": badge,
                "summary": result.get("summary", ""),
                "recommendation": result.get("recommendation", ""),
                "next_steps": result.get("next_steps", [])
            }
        except Exception as e:
            logger.error(f"Failed to generate seniority alignment: {e}")
            return {
                "your_level": your_level,
                "your_years": years_experience,
                "required_level": required_level,
                "required_years": required_years,
                "gap": gap,
                "alignment_status": alignment_status,
                "alignment_badge": badge,
                "summary": f"You have {years_experience} years of experience, but this role requires {required_years}+ years.",
                "recommendation": "Focus on highlighting transferable skills and quantifiable achievements.",
                "next_steps": [
                    "Highlight transferable skills",
                    "Target roles that match your experience level"
                ]
            }

