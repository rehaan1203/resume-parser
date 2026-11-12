"""Central orchestrator for the 4-Phase deterministic pipeline."""
from typing import Dict, Any
import asyncio
import uuid

# Phase 1
from app.utils.experience_extractor import (
    extract_candidate_experience_with_llm,
    extract_candidate_experience_unified,
    extract_required_experience_with_llm,
)
from app.utils.domain_detector import analyze_domain
from app.utils.skill_extractor import extract_skills, compare_skills

# Phase 2
from app.utils.score_calculator import calculate_skills_score, calculate_overall_score
from app.utils.seniority_calculator import calculate_seniority_score_and_gap
from app.utils.friction_generator import generate_friction_and_strengths

# Phase 4
from app.utils.cross_validator import validate_and_override

from app.config import settings
from app.utils.link_processor import LinkProcessor

class DeterministicOrchestrator:
    def __init__(self):

        self.link_processor = LinkProcessor()

    async def process(self, request_data: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        async def report(prog: int, msg: str):
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(prog, msg)
                else:
                    progress_callback(prog, msg)
            delay = getattr(settings, "orchestrator_progress_delay", 0.3)
            if delay > 0:
                await asyncio.sleep(delay)

        await report(5, "Parsing resume and job description...")
        resume_text = request_data.get("resume", "") or request_data.get("resume_text", "")
        jd_text = (
            request_data.get("jd_text", "")
            or request_data.get("jdText", "")
            or request_data.get("job_description", "")
            or request_data.get("jd", "")
        )
        
        # --- PHASE 1: Universal Hybrid Parser (Deterministic + Open-Domain LLM) ---
        await report(10, "Extracting and comparing skills...")
        from app.utils.skill_extractor import extract_open_domain_skills
        from app.ai.open_domain_extractor import OpenDomainExtractor
        from app.ai.client import GenAIClient

        open_domain_requested = bool(
            request_data.get("enable_open_domain")
            or request_data.get("enableOpenDomain")
            or len(jd_text.strip()) >= 140
        )

        resume_skills = extract_open_domain_skills(resume_text) if open_domain_requested else extract_skills(resume_text)
        jd_skills = extract_open_domain_skills(jd_text) if open_domain_requested else extract_skills(jd_text)

        domain_analysis = analyze_domain(resume_text, jd_text)
        resume_domain = domain_analysis.get("resume_domain", "unknown")
        jd_domain = domain_analysis.get("jd_domain", "unknown")
        is_compatible = domain_analysis.get("domain_match", False)

        open_domain_result = None
        if open_domain_requested and settings.use_ai_service:
            try:
                od_extractor = OpenDomainExtractor(GenAIClient())
                od_reqs = await od_extractor.extract_requirements(jd_text)
                if od_reqs:
                    open_domain_result = await od_extractor.evaluate_matches(od_reqs, resume_text)
                    if od_extractor.last_detected_domain:
                        domain_analysis["detected_role_domain"] = od_extractor.last_detected_domain
                    # Re-check domain compatibility if open-domain extraction found strong requirement alignment
                    if open_domain_result.weighted_score >= 45.0:
                        is_compatible = True
                        domain_analysis["domain_match"] = True
            except Exception as od_err:
                from app.utils.logger import logger
                logger.warning(f"Universal open-domain extraction fallback to deterministic skills: {od_err}")

        skills_detected = len(open_domain_result.requirements) if open_domain_result else len(jd_skills)

        # True mismatch only occurs if neither exact match nor compatible transition
        is_mismatch = (resume_domain != "unknown" and jd_domain != "unknown" and not is_compatible)
        is_unknown = (resume_domain == "unknown" or jd_domain == "unknown")
        domain_analysis["is_mismatch"] = is_mismatch
        domain_analysis["is_unknown"] = is_unknown

        if not jd_skills and not open_domain_result:
            await report(100, "No skills detected in Job Description.")
            return {
                "id": f"ai-{uuid.uuid4().hex[:8]}",
                "status": "unparseable_jd",
                "overall_score": None,
                "score_breakdown": {
                    "skills_match": None,
                    "seniority_match": None,
                    "domain_match": None
                },
                "domain_analysis": domain_analysis,
                "skill_analysis": {
                    "matching_skills": [],
                    "missing_skills": [],
                    "skills_score": 0,
                    "skills_detected": 0,
                    "low_confidence": True
                },
                "seniority_analysis": None,
                "seniority_assessed": None,
                "seniority_reason": None,
                "seniority_status": None,
                "skills_detected": 0,
                "low_confidence": True,
                "message": "We couldn't recognize specific requirements in this job description. This version works best with skill-based postings and has limited coverage for some fields, such as healthcare, law and trades, so your posting may be fine.",
                "friction_points": [],
                "strengths": [],
                "skill_gaps": [],
                "roadmap": None,
                "ats_optimization": None
            }

        if is_mismatch:
            DOMAIN_DISPLAY_NAMES = {
                "legal": "Lawyer/Legal Professional",
                "data_science": "AI/ML Engineer",
                "software_engineering": "Software Engineer",
                "finance": "Finance Professional",
                "marketing": "Marketing Professional",
                "sales": "Sales Professional",
                "hr": "HR Professional",
                "product": "Product Manager",
                "healthcare": "Healthcare Professional",
                "trades": "Skilled Trades Professional",
                "unknown": "Unknown Domain"
            }
            resume_display = DOMAIN_DISPLAY_NAMES.get(resume_domain, resume_domain.replace('_', ' ').title())
            jd_display = domain_analysis.get("detected_role_domain") or DOMAIN_DISPLAY_NAMES.get(jd_domain, jd_domain.replace('_', ' ').title())
            
            await report(20, "Generating mismatch explanation...")
            from app.ai.explainer import Phase3Explainer
            explainer = Phase3Explainer()
            llm_message = await explainer.generate_mismatch_message(resume_display, jd_display)
            
            await report(100, "Domain mismatch detected.")
            return {
                "id": f"ai-{uuid.uuid4().hex[:8]}",
                "status": "domain_mismatch",
                "resume_domain": resume_display,
                "jd_domain": jd_display,
                "overall_score": 0,
                "message": llm_message,
                "transition_available": True,
                "full_analysis": None
            }

        await report(15, "Detecting professional domain and extracting experience...")
        use_unified_exp = bool(open_domain_requested)
        cand_exp_task = (
            extract_candidate_experience_unified(resume_text)
            if use_unified_exp
            else extract_candidate_experience_with_llm(resume_text)
        )
        jd_exp_task = extract_required_experience_with_llm(jd_text)
        candidate_exp, jd_exp = await asyncio.gather(cand_exp_task, jd_exp_task)
        seniority_analysis = calculate_seniority_score_and_gap(candidate_exp, jd_exp)
        candidate_years = seniority_analysis.get("years_experience") or 0
        required_years = seniority_analysis.get("required_years") or 0

        if open_domain_result:
            matching_skills = list(open_domain_result.strengths)
            missing_skills = list(open_domain_result.skill_gaps)
            skills_score = int(round(open_domain_result.weighted_score))
        else:
            matching_skills, missing_skills = compare_skills(resume_skills, jd_skills)
            skills_score = calculate_skills_score(len(matching_skills), len(jd_skills))

        low_confidence = skills_detected < settings.low_evidence_threshold

        # --- PHASE 2: Centralized Calculator ---
        await report(20, "Calculating match score...")
        
        # Apply domain logic without penalizing overlapping engineering specializations (e.g. Python SWE -> AI Engineer)
        is_mismatch = domain_analysis.get("is_mismatch", False)
        is_transition = domain_analysis.get("is_compatible_transition", False)
        tech_family = {"software_engineering", "data_science", "product"}
        same_tech_family = (resume_domain in tech_family and jd_domain in tech_family and skills_score >= 40)
        
        if is_mismatch:
            overall_score = 0
        elif is_transition and not same_tech_family:
            base_score = calculate_overall_score(skills_score, seniority_analysis.get("seniority_score"))
            overall_score = round(base_score * 0.95) if base_score is not None else skills_score
        else:
            overall_score = calculate_overall_score(skills_score, seniority_analysis.get("seniority_score"))
        
        await report(25, "Analyzing skill gaps...")
        friction_data = generate_friction_and_strengths(
            matching_skills=matching_skills,
            missing_skills=missing_skills,
            seniority_gap=seniority_analysis.get("gap"),
            candidate_years=candidate_years,
            required_years=required_years,
            domain_analysis=domain_analysis
        )
        
        # --- PHASE 3: LLM Explains ---
        await report(30, "Preparing data for insights...")
        from app.ai.explainer import Phase3Explainer
        explainer = Phase3Explainer()
        
        # Determine gap type based on overall score or missing skills for roadmap
        gap_type = "standard_upskill"
        if domain_analysis.get("is_mismatch"):
            gap_type = "career_change"
        elif domain_analysis.get("is_compatible_transition"):
            gap_type = "role_specialization"
        elif overall_score >= 90:
            gap_type = "mini_upskill"
        elif overall_score >= 70:
            gap_type = "short_upskill"
        elif overall_score < 50:
            gap_type = "extended_upskill"

        # Retrieve RAG verified phrasing templates for ATS optimization
        rag_phrasing_templates = []
        try:
            from app.knowledge.retriever import get_retriever
            target_domain = jd_domain if jd_domain and jd_domain != "unknown" else None
            tmpl_objs = await get_retriever().get_phrasing_templates_for_gaps(
                skills=missing_skills,
                domain=target_domain,
                limit=3
            )
            rag_phrasing_templates = [t.model_dump() for t in tmpl_objs]
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"RAG phrasing template retrieval failed: {e}")

        # Prepare consolidated coroutines for Phase 3 (reduces 4 calls -> 2 calls)
        from app.utils.document_chunker import extract_core_sections
        resume_excerpt = extract_core_sections(resume_text, doc_type="resume", max_chars=2500)
        target_role = str(domain_analysis.get("detected_role_domain") or "").strip()
        if not target_role and jd_text.strip():
            target_role = jd_text.strip().splitlines()[0][:80].strip()

        coros = {
            "holistic": explainer.generate_holistic_insights(
                score=overall_score,
                strengths=matching_skills,
                gaps=missing_skills,
                years_experience=seniority_analysis.get("years_experience") or 0,
                required_years=seniority_analysis.get("required_years") or 0,
                your_level=seniority_analysis.get("your_level") or "Entry",
                required_level=seniority_analysis.get("required_level") or "Entry",
                seniority_gap=seniority_analysis.get("gap") if seniority_analysis.get("gap") is not None else 0,
                seniority_assessed=seniority_analysis.get("seniority_assessed", True),
                domain_analysis=domain_analysis,
                phrasing_templates=rag_phrasing_templates if rag_phrasing_templates else None,
                resume_excerpt=resume_excerpt,
            )
        }
        
        if missing_skills and overall_score < 95:
            # Query RAG catalog for verified resources matching missing skills and domain
            verified_rag_resources = []
            try:
                from app.knowledge.retriever import get_retriever
                target_domain = jd_domain if jd_domain and jd_domain != "unknown" else None
                candidate_lvl = seniority_analysis.get("your_level", "Mid")
                search_results = await get_retriever().search_for_gaps(
                    skills=missing_skills,
                    domain=target_domain,
                    limit=8,
                    seniority=candidate_lvl,
                    is_career_transition=domain_analysis.get("is_mismatch", False) or domain_analysis.get("is_compatible_transition", False),
                    known_skills=matching_skills,
                    context_text=jd_text,
                )
                verified_rag_resources = [r.model_dump() for r in search_results]
            except Exception as e:
                from app.utils.logger import logger
                logger.warning(f"RAG resource retrieval failed: {e}. Falling back to default generation.")

            coros["roadmap"] = explainer.generate_roadmap(
                missing_skills,
                gap_type,
                verified_resources=verified_rag_resources if verified_rag_resources else None,
                target_role=target_role,
            )
            
        # Background task for incremental progress
        async def progress_updater():
            try:
                progress = 30
                while progress < 80:
                    await asyncio.sleep(1.0)
                    progress += 5
                    await report(progress, f"Generating personalized insights... ({progress}%)")
            except asyncio.CancelledError:
                pass
                
        updater_task = asyncio.create_task(progress_updater())
            
        # Run consolidated Phase 3 generators with rate-limited pacing and exception shielding
        keys = list(coros.keys())
        raw_results = await asyncio.gather(*coros.values(), return_exceptions=True)
        
        # Cancel the updater once generation finishes
        updater_task.cancel()
        
        phase3_results = {}
        for key, res in zip(keys, raw_results):
            if isinstance(res, Exception):
                from app.utils.logger import logger
                logger.warning(f"Phase 3 insight '{key}' generation encountered error: {res}. Using graceful fallback.")
                if key == "holistic":
                    phase3_results[key] = {
                        "executive_summary": f"Candidate profile evaluated against target role requirements. Technical alignment score: {overall_score}%.",
                        "ats_optimization": {"summary": "ATS optimization complete.", "keywords": missing_skills[:5], "phrasing": [], "formatting_tips": []},
                        "seniority_alignment": {"alignment_summary": "Candidate experience evaluated against role seniority.", "advice": "Target key role competencies."},
                    }
                elif key == "roadmap":
                    phase3_results[key] = {"type": "standard_upskill", "title": "Targeted Upskilling Roadmap", "weeks": []}
            else:
                phase3_results[key] = res
        
        holistic_data = phase3_results.get("holistic") or {}
        executive_summary = holistic_data.get("executive_summary", f"Candidate achieved a {overall_score}% match.")
        ats_optimization = holistic_data.get("ats_optimization")
        seniority_alignment = holistic_data.get("seniority_alignment")
        roadmap = phase3_results.get("roadmap", None)
        
        await report(85, "")
        from app.utils.logger import logger
        link_tasks = {}
        if roadmap:
            link_tasks["roadmap"] = self.link_processor.process_response(roadmap)
        if ats_optimization:
            link_tasks["ats"] = self.link_processor.process_response(ats_optimization)
        if seniority_alignment:
            link_tasks["seniority"] = self.link_processor.process_response(seniority_alignment)

        if link_tasks:
            logger.info("🔗 Validating and processing report links concurrently...")
            lp_keys = list(link_tasks.keys())
            lp_results = await asyncio.gather(*link_tasks.values())
            processed_links = dict(zip(lp_keys, lp_results))
            if "roadmap" in processed_links:
                roadmap = processed_links["roadmap"]
            if "ats" in processed_links:
                ats_optimization = processed_links["ats"]
            if "seniority" in processed_links:
                seniority_alignment = processed_links["seniority"]
                seniority_analysis.update(seniority_alignment)

        logger.info("✅ Link processing complete")
            
        domain_match_val = (
            None if (resume_domain == "unknown" and jd_domain == "unknown")
            else (100 if domain_analysis.get("is_exact_match", False) else (85 if domain_analysis.get("is_compatible_transition", False) else (100 if domain_analysis.get("domain_match") else 0)))
        )

        # Build raw payload
        raw_payload = {
            "id": f"ai-{uuid.uuid4().hex[:8]}",
            "skills_detected": skills_detected,
            "low_confidence": low_confidence,
            "executive_summary": executive_summary,
            "overall_score": overall_score,
            "score_breakdown": {
                "skills_match": skills_score,
                "seniority_match": seniority_analysis.get("seniority_score"),
                "domain_match": domain_match_val
            },
            "domain_analysis": domain_analysis,
            "skill_analysis": {
                "matching_skills": matching_skills,
                "missing_skills": missing_skills,
                "skills_score": skills_score,
                "skills_detected": skills_detected,
                "low_confidence": low_confidence
            },
            "seniority_analysis": seniority_analysis,
            "seniority_assessed": seniority_analysis.get("seniority_assessed", True),
            "seniority_reason": seniority_analysis.get("seniority_reason"),
            "seniority_status": seniority_analysis.get("seniority_status"),
            "friction_points": friction_data["friction_points"],
            "strengths": friction_data["strengths"],
            "skill_gaps": friction_data["skill_gaps"],
            "ats_optimization": ats_optimization,
            "roadmap": roadmap,
            "degraded_sections": getattr(explainer, "degraded_sections", [])
        }
        
        # --- PHASE 4: Cross-Validation ---
        await report(90, "Cross-validating final results...")
        final_payload = validate_and_override(raw_payload)
        
        await report(100, "Analysis complete.")
        return final_payload

    async def generate_transition_analysis(
        self, 
        resume: str, 
        jd: str, 
        resume_domain: str, 
        jd_domain: str
    ) -> Dict[str, Any]:
        """Generate a full transition analysis on demand."""
        from app.ai.explainer import Phase3Explainer
        from app.utils.logger import logger
        
        logger.info(f"Generating transition analysis for {resume_domain} -> {jd_domain}")
        explainer = Phase3Explainer()
        
        # We need a domain analysis dict for the explainer
        domain_analysis = {
            "resume_domain": resume_domain,
            "jd_domain": jd_domain,
            "is_mismatch": True,
            "domain_match": False
        }
        
        # We simulate skill gaps for the career change (e.g. foundational skills of the new domain)
        # Normally Phase 1 extracts these, but here we can just query the explainer to generate the roadmap based on the domains
        coros = {
            "roadmap": explainer.generate_roadmap([jd_domain], gap_type="career_change"),
            "ats_optimization": explainer.generate_ats_optimization(
                gaps=["foundational skills"], 
                jd_text=jd, 
                domain_analysis=domain_analysis
            ),
            "seniority_alignment": explainer.generate_seniority_alignment(
                years_experience=0,
                required_years=0,
                your_level="N/A",
                required_level="N/A",
                gap=0,
                domain_analysis=domain_analysis
            )
        }
        
        keys = list(coros.keys())
        results = await asyncio.gather(*coros.values())
        phase3_results = dict(zip(keys, results))
        
        roadmap = phase3_results["roadmap"]
        ats_optimization = phase3_results["ats_optimization"]
        seniority_alignment = phase3_results["seniority_alignment"]
        
        if roadmap:
            roadmap = await self.link_processor.process_response(roadmap)
        if ats_optimization:
            ats_optimization = await self.link_processor.process_response(ats_optimization)
        if seniority_alignment:
            seniority_alignment = await self.link_processor.process_response(seniority_alignment)
            
        return {
            "status": "success",
            "score": 0,
            "domain_match": False,
            "roadmap": roadmap,
            "ats_optimization": ats_optimization,
            "seniority_analysis": seniority_alignment
        }
