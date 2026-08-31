"""Phase 3 LLM Explainer - generates explanations based on fixed deterministic data."""
import asyncio
from typing import Dict, Any, List
from app.ai.client import GenAIClient
from app.utils.logger import logger

class Phase3Explainer:
    def __init__(self):
        self.client = GenAIClient()
        
    async def generate_executive_summary(self, score: int, strengths: List[str], gaps: List[str], seniority_gap: int) -> str:
        prompt = f"""
        Write a concise, professional 3-4 sentence executive summary for a candidate.
        They scored {score}% on the job match.
        Their key strengths are: {', '.join(strengths[:3])}.
        Their key skill gaps are: {', '.join(gaps[:3])}.
        They have a seniority gap of {seniority_gap} years (0 means no gap).
        
        Keep it objective, highlighting strengths and mentioning areas for growth. Do not invent new skills or facts.
        """
        
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
        prompt = f"""
        Provide a concise, 2-sentence explanation of why a candidate with a {resume_domain} background is fundamentally mismatched for a {jd_domain} role. 
        Focus on the completely different core competencies and daily responsibilities required.
        """
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
            prompt = f"""
            Provide specific, actionable Career Transition ATS optimization tips for a candidate moving from {resume_domain} to {jd_domain}.
            Missing technical skills: {', '.join(gaps)}
            
            Output format exactly:
            1. 'keywords': A list of foundational keywords they should learn and add (e.g., "Add 'Python' to Core Competencies").
            2. 'phrasing': A list of objects with 'original' and 'suggested' bullet points demonstrating how to translate {resume_domain} experience into transferable skills for {jd_domain}.
            3. 'formatting_tips': 2-3 standard ATS formatting tips (e.g. use functional resume format).
            """
        else:
            prompt = f"""
        Provide specific, actionable ATS optimization tips based on the candidate's skill gaps.
        Skill gaps: {', '.join(gaps)}
        
        Output format exactly:
        1. 'keywords': A list of specific keywords they should add (e.g., "Add 'Technology Law' to Core Competencies").
        2. 'phrasing': A list of objects with 'original' and 'suggested' bullet points demonstrating how to rewrite experience to highlight the missing skills.
        3. 'formatting_tips': 2-3 standard ATS formatting tips.
        
        Do not invent requirements not related to the gaps.
        """
        
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
            
        prompt = f"""
        Generate a highly structured, non-repeating learning roadmap for a candidate missing these skills: {', '.join(gaps)}.
        The roadmap must be EXACTLY {weeks_count} weeks long. Every single day in those weeks must have unique content and at least one real-world resource link (e.g., Coursera, YouTube, official docs).
        
        CRITICAL TOKEN LIMIT: To prevent truncation for long {weeks_count}-week roadmaps, you MUST keep every 'action' description concise (under 20 words) and provide 1-2 highly relevant URLs per day. Do not add any extra commentary.
        
        Output format:
        - type: "{gap_type}"
        - title: "Upskill Roadmap ({weeks_count} Weeks)"
        - weeks: List of week objects, each containing:
            - week: week number
            - focus: week theme
            - days: List of 7 day objects (for that week), each containing:
                - day: absolute day number (1, 2, ..., {weeks_count * 7})
                - action: what to do
                - resources: list of URLs
                - estimated_time: string (e.g., "2 hours")
        """
        
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

        prompt = f"""
        You are a seniority alignment analyzer.
        
        INPUT DATA:
        - Your Experience: {years_experience} years
        - Required Experience: {required_years} years
        - Your Level: {your_level}
        - Required Level: {required_level}
        - Experience Gap: {gap} years
        - Alignment Status: {alignment_status}
        
        TASK:
        Generate a comprehensive seniority alignment section with:
        
        1. SUMMARY: A single, punchy sentence (max 15 words) explaining the gap and what it means for the candidate.
        2. RECOMMENDATION: Specific advice on what level roles to target and how to bridge the gap.
        3. NEXT STEPS: 3-5 actionable steps to bridge the gap.
        
        Return exactly this JSON schema:
        {{
          "summary": "string",
          "recommendation": "string",
          "next_steps": ["string"]
        }}
        """
        
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

