"""Phase 3 LLM Explainer - generates explanations based on fixed deterministic data."""
import asyncio
from typing import Dict, Any, List
from app.ai.client import GenAIClient
from app.utils.logger import logger
from app.prompts.analysis_prompt import build_executive_summary_prompt, build_mismatch_prompt
from app.prompts.ats_prompt import build_standard_ats_prompt, build_transition_ats_prompt, build_rag_ats_prompt
from app.prompts.roadmap_prompt import build_upskill_roadmap_prompt, build_rag_upskill_roadmap_prompt, get_roadmap_weeks_count
from app.prompts.seniority_prompt import build_seniority_alignment_prompt

class Phase3Explainer:
    def __init__(self):
        self.client = GenAIClient()
        self.degraded_sections: List[str] = []
        
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
            if "executive_summary" not in self.degraded_sections:
                self.degraded_sections.append("executive_summary")
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
            if "mismatch_message" not in self.degraded_sections:
                self.degraded_sections.append("mismatch_message")
            return f"Your experience is in {resume_domain}, but this role requires {jd_domain}."

    async def generate_ats_optimization(
        self,
        gaps: List[str],
        jd_text: str,
        domain_analysis: Dict[str, Any] = None,
        phrasing_templates: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        is_mismatch = domain_analysis and domain_analysis.get("is_mismatch", False)
        transition_bridge_info = None
        if is_mismatch:
            resume_domain = domain_analysis.get("resume_domain", "").replace("_", " ").title()
            jd_domain = domain_analysis.get("jd_domain", "").replace("_", " ").title()
            
            # Retrieve RAG Transition Bridge for mismatch
            try:
                from app.knowledge.retriever import get_retriever
                bridge = get_retriever().get_transition_bridge(domain_analysis.get("resume_domain"), domain_analysis.get("jd_domain"))
                if bridge:
                    transition_bridge_info = bridge.model_dump()
            except Exception as e:
                logger.warning(f"Failed to retrieve transition bridge in explainer: {e}")

            prompt = build_transition_ats_prompt(
                resume_domain=resume_domain,
                jd_domain=jd_domain,
                gaps=gaps,
                transition_bridge=transition_bridge_info
            )
        elif phrasing_templates:
            prompt = build_rag_ats_prompt(gaps=gaps, phrasing_templates=phrasing_templates)
        else:
            prompt = build_standard_ats_prompt(gaps=gaps)
        
        try:
            res = await self.client.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "keywords": ["string"],
                    "phrasing": [{"original": "string", "suggested": "string"}],
                    "formatting_tips": ["string"]
                }
            )
            if transition_bridge_info and isinstance(res, dict):
                res["transition_bridge"] = transition_bridge_info
            if phrasing_templates and isinstance(res, dict):
                res["proven_templates"] = phrasing_templates
            return res
        except Exception as e:
            logger.error(f"Failed to generate ATS optimization: {e}")
            if "ats_optimization" not in self.degraded_sections:
                self.degraded_sections.append("ats_optimization")
            fallback = {
                "keywords": [f"Add '{gap}' to Core Competencies" for gap in gaps[:3]],
                "phrasing": [],
                "formatting_tips": ["Use standard section headings", "Avoid tables and complex formatting"]
            }
            if phrasing_templates:
                fallback["proven_templates"] = phrasing_templates
            return fallback

    async def generate_roadmap(
        self,
        gaps: List[str],
        gap_type: str = "standard_upskill",
        verified_resources: List[Dict[str, Any]] = None,
        target_role: str = "",
    ) -> Dict[str, Any]:
        """Generate a structured learning roadmap based on gap type and verified catalog resources."""
        weeks_count = get_roadmap_weeks_count(gap_type)
        if verified_resources or target_role:
            # Compress marketing fluff from descriptions before sending to LLM prompt
            compressed_resources = None
            if verified_resources:
                try:
                    from app.knowledge.compressor import get_contextual_compressor
                    compressor = get_contextual_compressor()
                    compressed_resources = []
                    for r in verified_resources:
                        item_copy = dict(r)
                        if "description" in item_copy:
                            item_copy["description"] = compressor.compress_description(item_copy["description"])
                        compressed_resources.append(item_copy)
                except Exception:
                    compressed_resources = verified_resources

            prompt = build_rag_upskill_roadmap_prompt(
                gaps=gaps,
                gap_type=gap_type,
                verified_resources=compressed_resources,
                target_role=target_role,
            )
        else:
            prompt = build_upskill_roadmap_prompt(gaps=gaps, gap_type=gap_type)
        
        try:
            result = await self.client.generate_structured_content(
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
            if verified_resources and isinstance(result, dict):
                result["verified_resources"] = verified_resources

                # Attach matched multi-modal architecture diagrams
                try:
                    from app.knowledge.retriever import get_retriever
                    matched_diags = get_retriever().get_diagrams_for_skills(gaps, limit=2)
                    if matched_diags:
                        result["architecture_diagrams"] = [d.model_dump() for d in matched_diags]
                except Exception as diag_err:
                    logger.debug(f"Architecture diagram retrieval skipped: {diag_err}")

            return result
        except Exception as e:
            logger.error(f"Failed to generate roadmap: {e}")
            if "roadmap" not in self.degraded_sections:
                self.degraded_sections.append("roadmap")
            fallback = {
                "type": gap_type,
                "title": f"Fallback Roadmap ({weeks_count} Weeks)",
                "weeks": []
            }
            if verified_resources:
                fallback["verified_resources"] = verified_resources
            return fallback

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
            if "seniority_alignment" not in self.degraded_sections:
                self.degraded_sections.append("seniority_alignment")
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

    async def generate_holistic_insights(
        self,
        score: int,
        strengths: List[str],
        gaps: List[str],
        years_experience: int,
        required_years: int,
        your_level: str,
        required_level: str,
        seniority_gap: int,
        seniority_assessed: bool = True,
        domain_analysis: Dict[str, Any] = None,
        phrasing_templates: List[Dict[str, Any]] = None,
        resume_excerpt: str = "",
    ) -> Dict[str, Any]:
        """
        Consolidated single-call synthesis of Executive Summary, ATS Optimization, and Seniority Alignment.
        Reduces Phase 3 LLM calls from 3 -> 1 to eliminate API burst rate limits and speed up evaluation.
        """
        is_mismatch = bool(domain_analysis and domain_analysis.get("is_mismatch", False))
        transition_bridge_info = None
        if is_mismatch:
            try:
                from app.knowledge.retriever import get_retriever
                bridge = get_retriever().get_transition_bridge(
                    domain_analysis.get("resume_domain"), domain_analysis.get("jd_domain")
                )
                if bridge:
                    transition_bridge_info = bridge.model_dump()
            except Exception as e:
                logger.warning(f"Failed to retrieve transition bridge: {e}")

        if seniority_gap <= 0:
            alignment_status, badge = "match", "✅ PERFECT MATCH"
        elif seniority_gap <= 2:
            alignment_status, badge = "minor_gap", "🟡 MINOR GAP"
        else:
            alignment_status, badge = "significant_gap", "🔴 SIGNIFICANT GAP"

        templates_hint = ""
        if phrasing_templates:
            lines = [
                f"- Verbs: {', '.join(t.get('action_verbs', [])[:3])} | Pattern: {t.get('star_template', '')}"
                for t in phrasing_templates[:3]
            ]
            templates_hint = "\nPROVEN STAR BULLET TEMPLATES:\n" + "\n".join(lines)

        domain_note = ""
        if domain_analysis:
            r_dom = str(domain_analysis.get("resume_domain", "unknown")).replace("_", " ").title()
            detected_role = str(domain_analysis.get("detected_role_domain") or "").strip()
            j_dom = detected_role or str(domain_analysis.get("jd_domain", "unknown")).replace("_", " ").title()
            domain_pct = (
                100
                if domain_analysis.get("is_exact_match", False)
                else (85 if domain_analysis.get("is_compatible_transition", False) else (100 if domain_analysis.get("domain_match") else 0))
            )
            if is_mismatch:
                domain_note = f"Domain Context: Significant domain shift from {r_dom} to {j_dom} (emphasize transferable skills)."
            elif domain_analysis.get("is_compatible_transition", False):
                domain_note = (
                    f"Domain Alignment: Compatible technical transition ({r_dom} -> {j_dom}, {domain_pct}% Domain Match). "
                    "Domains are compatible — NEVER write 'domain mismatch' or claim the candidate's domain conflicts with the role."
                )
            else:
                domain_note = (
                    f"Domain Alignment: Direct domain fit ({j_dom}, {domain_pct}% Domain Match). "
                    "Do NOT state there is a domain mismatch."
                )

        resume_hint = ""
        if resume_excerpt:
            resume_hint = f"\nCANDIDATE RESUME EXCERPT:\n{resume_excerpt[:2500]}\n"

        seniority_rule = (
            "Seniority gap is <= 0; candidate meets or exceeds the experience baseline."
            if seniority_gap <= 0
            else f"Candidate has a {seniority_gap}-year experience SHORTFALL below {required_level} ({required_years} yrs). Do NOT write that candidate experience 'aligns with' or 'meets' the required level."
        )

        prompt = f"""
Analyze this candidate evaluation and produce a unified recruiter evaluation JSON.
- Overall Match Score: {score}%
- Key Strengths: {', '.join(strengths[:8]) or 'Foundational skills'}
- Priority Skill Gaps: {', '.join(gaps[:8]) or 'None'}
- Experience: {years_experience} yrs ({your_level}) vs Required {required_years} yrs ({required_level}), gap={seniority_gap} yrs ({alignment_status})
- {seniority_rule}
- {domain_note}{templates_hint}{resume_hint}

Instructions:
1. executive_summary: Concise 2-3 sentence recruiter verdict citing exact strengths, priority gaps, and seniority gap/shortfall accurately. Strictly obey the Domain Alignment note (do NOT claim a domain mismatch if domains are compatible or matched) and never call a positive seniority gap an alignment.
2. ats_optimization:
   - keywords: 5-8 high-impact technical keywords to add aligned with the priority gaps.
   - phrasing: 3 bullet upgrades ({{original, suggested}}). Anchor 'original' in real responsibilities/skills from the Candidate Resume Excerpt (or baseline matched skills if brief), and use STAR action verbs with bracketed metric placeholders like [X]%, [N]+, or [Y]ms when exact numbers are not in the resume (NEVER invent fake percentages like 30%, 40%, or 25%).
   - formatting_tips: 3 actionable ATS formatting tips.
3. seniority_alignment:
   - summary: Clear 1-2 sentence assessment of years/tier fit accurately stating any gap or shortfall (never describe a shortfall as 'aligns with' the requirement).
   - recommendation: Actionable career positioning advice.
   - next_steps: 2-3 concrete steps.
"""
        schema = {
            "executive_summary": "string",
            "ats_optimization": {
                "keywords": ["string"],
                "phrasing": [{"original": "string", "suggested": "string"}],
                "formatting_tips": ["string"],
            },
            "seniority_alignment": {
                "summary": "string",
                "recommendation": "string",
                "next_steps": ["string"],
            },
        }

        try:
            res = await self.client.generate_structured_content(prompt=prompt, output_schema=schema, temperature=0.1)
            exec_summary = res.get("executive_summary") or f"Candidate achieved a {score}% match."
            ats_opt = res.get("ats_optimization") if isinstance(res.get("ats_optimization"), dict) else {}
            ats_opt.setdefault("keywords", [f"Add '{g}' to Core Competencies" for g in gaps[:3]])
            ats_opt.setdefault("phrasing", [])
            ats_opt.setdefault("formatting_tips", ["Use standard section headings", "Quantify outcomes with metrics"])
            if transition_bridge_info:
                ats_opt["transition_bridge"] = transition_bridge_info
            if phrasing_templates:
                ats_opt["proven_templates"] = phrasing_templates

            sen_raw = res.get("seniority_alignment") if isinstance(res.get("seniority_alignment"), dict) else {}
            sen_out = None
            if seniority_assessed:
                sen_out = {
                    "your_level": your_level,
                    "your_years": years_experience,
                    "required_level": required_level,
                    "required_years": required_years,
                    "gap": seniority_gap,
                    "alignment_status": alignment_status,
                    "alignment_badge": badge,
                    "summary": sen_raw.get("summary") or f"Candidate has {years_experience} yrs vs {required_years}+ yrs required.",
                    "recommendation": sen_raw.get("recommendation") or "Highlight transferable technical ownership and measurable outcomes.",
                    "next_steps": sen_raw.get("next_steps") or ["Highlight transferable skills", "Showcase production impact"],
                }

            return {
                "executive_summary": exec_summary,
                "ats_optimization": ats_opt,
                "seniority_alignment": sen_out,
            }
        except Exception as e:
            logger.error(f"Holistic insights generation failed ({e}); degrading cleanly.")
            for sec in ("executive_summary", "ats_optimization", "seniority_alignment"):
                if sec not in self.degraded_sections:
                    self.degraded_sections.append(sec)
            ats_fallback = {
                "keywords": [f"Add '{g}' to Core Competencies" for g in gaps[:5]],
                "phrasing": [],
                "formatting_tips": ["Use standard section headings", "Avoid tables and complex graphics"],
            }
            if phrasing_templates:
                ats_fallback["proven_templates"] = phrasing_templates
            return {
                "executive_summary": f"Candidate achieved a {score}% match. Key strengths: {', '.join(strengths[:3])}. Key gaps: {', '.join(gaps[:3])}.",
                "ats_optimization": ats_fallback,
                "seniority_alignment": {
                    "your_level": your_level,
                    "your_years": years_experience,
                    "required_level": required_level,
                    "required_years": required_years,
                    "gap": seniority_gap,
                    "alignment_status": alignment_status,
                    "alignment_badge": badge,
                    "summary": f"You have {years_experience} years of experience, while this role prefers {required_years}+ years.",
                    "recommendation": "Highlight transferable technical experience and project impact.",
                    "next_steps": ["Highlight transferable skills", "Close top priority skill gaps"],
                } if seniority_assessed else None,
            }


