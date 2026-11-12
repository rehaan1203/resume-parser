"""Long-term career guidance based on resume analysis and RAG Knowledge Base."""
from typing import Dict, Any, Optional
from app.ai.client import GenAIClient
from app.prompts.career_prompt import CAREER_ADVICE_PROMPT, CAREER_ADVICE_RAG_PROMPT
from app.knowledge.retriever import KnowledgeRetriever
from app.utils.document_chunker import extract_core_sections
from app.utils.logger import logger

class CareerAdvisor:
    """Provide long-term career guidance grounded in verified knowledge base resources."""

    def __init__(self, client: GenAIClient, retriever: Optional[KnowledgeRetriever] = None):
        self.client = client
        self.retriever = retriever or KnowledgeRetriever()
        self.is_fallback = False

    async def get_advice(
        self,
        resume: str,
        experience: str,
        goals: str,
        skill_gaps: list,
        domain: str = "tech",
        source_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate career advice grounded in verified resources and transition bridge knowledge."""
        verified_resources_map: Dict[str, list] = {}
        verified_summary_lines = []
        transition_bridge_info = None

        try:
            # 1. Retrieve transition bridge if candidate is changing domains
            if source_domain and source_domain.lower() != domain.lower():
                bridge = self.retriever.get_transition_bridge(source_domain, domain)
                if bridge:
                    transition_bridge_info = bridge.model_dump()
                    verified_summary_lines.append(f"TRANSITION BRIDGE: Moving from {bridge.source_domain.title()} to {bridge.target_domain.title()}")
                    verified_summary_lines.append(f"- Transferable Strengths: {', '.join(bridge.transferable_strengths)}")
                    verified_summary_lines.append(f"- Bridge Credentials: {', '.join(bridge.bridge_certifications)}")
                    verified_summary_lines.append(f"- Repositioning Strategy: {bridge.strategic_advice}")

            # 2. Retrieve verified resources for skill gaps
            verified_resources_map = await self.retriever.retrieve_for_skill_gaps(skill_gaps, domain=domain)
            for gap, res_list in verified_resources_map.items():
                for r in res_list:
                    verified_summary_lines.append(f"- Skill: {gap} | Title: {r.get('title')} | Platform: {r.get('platform')} | URL: {r.get('url')}")
        except Exception as e:
            logger.warning(f"RAG Knowledge Base retrieval skipped on exception: {e}")

        try:
            self.is_fallback = False
            prepared_resume = extract_core_sections(resume, doc_type="resume", max_chars=4000)
            if verified_summary_lines:
                prompt = CAREER_ADVICE_RAG_PROMPT.format(
                    resume=prepared_resume,
                    experience=experience[:500] if experience else "Not specified",
                    goals=goals[:500] if goals else "Career growth",
                    skill_gaps=", ".join(skill_gaps[:5]) if skill_gaps else "None",
                    verified_resources="\n".join(verified_summary_lines)
                )
            else:
                prompt = CAREER_ADVICE_PROMPT.format(
                    resume=prepared_resume,
                    experience=experience[:500] if experience else "Not specified",
                    goals=goals[:500] if goals else "Career growth"
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
            advice = result.get("advice", {})

            # Ground skill resources with verified URLs if model left them empty or generic
            for item in advice.get("skills_to_develop", []):
                skill_name = item.get("skill", "")
                matching_res = verified_resources_map.get(skill_name) or []
                if matching_res:
                    item["verified_resources"] = matching_res
                    if not item.get("resources"):
                        item["resources"] = [r["url"] for r in matching_res]

            advice["verified_resources_map"] = verified_resources_map
            if transition_bridge_info:
                advice["transition_bridge"] = transition_bridge_info
            return advice

        except Exception as e:
            logger.error(f"Career advice generation failed: {e}")
            self.is_fallback = True
            fallback = self._get_default_advice(skill_gaps)
            fallback["verified_resources_map"] = verified_resources_map
            if transition_bridge_info:
                fallback["transition_bridge"] = transition_bridge_info
            return fallback

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
