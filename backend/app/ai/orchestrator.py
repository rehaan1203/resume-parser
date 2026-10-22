"""Central orchestrator for the 4-Phase deterministic pipeline."""
from typing import Dict, Any
import asyncio
import uuid

# Phase 1
from app.utils.experience_extractor import extract_years_experience
from app.utils.domain_detector import analyze_domain
from app.utils.skill_extractor import extract_skills, compare_skills

# Phase 2
from app.utils.score_calculator import calculate_skills_score, calculate_overall_score
from app.utils.seniority_calculator import calculate_seniority_score_and_gap
from app.utils.friction_generator import generate_friction_and_strengths

# Phase 4
from app.utils.cross_validator import validate_and_override

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

        await report(5, "Parsing resume and job description...")
        await asyncio.sleep(0.3)
        resume_text = request_data.get("resume", "") or request_data.get("resume_text", "")
        jd_text = request_data.get("jd_text", "") or request_data.get("job_description", "")
        
        # --- PHASE 1: Deterministic Parser ---
        await report(10, "Detecting professional domain...")
        await asyncio.sleep(0.3)
        candidate_years = await extract_years_experience(resume_text)
        required_years = await extract_years_experience(jd_text)
        if required_years == 0:
            required_years = 3 # default fallback for JD if not found
            
        domain_analysis = analyze_domain(resume_text, jd_text)
        resume_domain = domain_analysis.get("resume_domain", "unknown")
        jd_domain = domain_analysis.get("jd_domain", "unknown")
        is_mismatch = (resume_domain != "unknown" and jd_domain != "unknown" and resume_domain != jd_domain)
        is_unknown = (resume_domain == "unknown" or jd_domain == "unknown")
        
        domain_analysis["is_mismatch"] = is_mismatch
        domain_analysis["is_unknown"] = is_unknown

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
                "unknown": "Unknown Domain"
            }
            resume_display = DOMAIN_DISPLAY_NAMES.get(resume_domain, resume_domain.replace('_', ' ').title())
            jd_display = DOMAIN_DISPLAY_NAMES.get(jd_domain, jd_domain.replace('_', ' ').title())
            
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
        
        await report(15, "Extracting and comparing skills...")
        await asyncio.sleep(0.3)
        resume_skills = extract_skills(resume_text)
        jd_skills = extract_skills(jd_text)
        skills_detected = len(jd_skills)

        if not jd_skills:
            await report(100, "No skills detected in Job Description.")
            return {
                "id": f"ai-{uuid.uuid4().hex[:8]}",
                "status": "unparseable_jd",
                "overall_score": None,
                "score_breakdown": {
                    "skills_match": 0,
                    "seniority_match": 0,
                    "domain_match": 100 if domain_analysis.get("domain_match") else 0
                },
                "domain_analysis": domain_analysis,
                "skill_analysis": {
                    "matching_skills": [],
                    "missing_skills": [],
                    "skills_score": 0,
                    "skills_detected": 0,
                    "low_confidence": True
                },
                "skills_detected": 0,
                "low_confidence": True,
                "message": "No technical skills or core requirements could be identified in the provided Job Description. Please provide a more detailed job posting.",
                "friction_points": [],
                "strengths": [],
                "skill_gaps": [],
                "roadmap": None,
                "ats_optimization": None
            }

        matching_skills, missing_skills = compare_skills(resume_skills, jd_skills)
        from app.config import settings
        low_confidence = skills_detected < settings.low_evidence_threshold

        # --- PHASE 2: Centralized Calculator ---
        await report(20, "Calculating match score...")
        await asyncio.sleep(0.3)
        skills_score = calculate_skills_score(len(matching_skills), len(jd_skills))
        seniority_analysis = calculate_seniority_score_and_gap(candidate_years, required_years)
        
        # Apply domain mismatch penalty (already checked for early return, but kept for unknown mismatch logic)
        is_mismatch = domain_analysis.get("is_mismatch", False)
        
        if is_mismatch:
            overall_score = 0
        else:
            overall_score = calculate_overall_score(skills_score, seniority_analysis["seniority_score"])
        
        await report(25, "Analyzing skill gaps...")
        await asyncio.sleep(0.3)
        friction_data = generate_friction_and_strengths(
            matching_skills=matching_skills,
            missing_skills=missing_skills,
            seniority_gap=seniority_analysis["gap"],
            candidate_years=candidate_years,
            required_years=required_years,
            domain_analysis=domain_analysis
        )
        
        # --- PHASE 3: LLM Explains ---
        await report(30, "Preparing data for insights...")
        await asyncio.sleep(0.3)
        from app.ai.explainer import Phase3Explainer
        explainer = Phase3Explainer()
        
        # Determine gap type based on overall score or missing skills for roadmap
        gap_type = "standard_upskill"
        if domain_analysis.get("is_mismatch"):
            gap_type = "career_change"
        elif overall_score >= 90:
            gap_type = "mini_upskill"
        elif overall_score >= 70:
            gap_type = "short_upskill"
        elif overall_score < 50:
            gap_type = "extended_upskill"

        # Prepare coroutines for Phase 3
        coros = {
            "executive_summary": explainer.generate_executive_summary(
                score=overall_score,
                strengths=matching_skills,
                gaps=missing_skills,
                seniority_gap=seniority_analysis["gap"]
            ),
            "ats_optimization": explainer.generate_ats_optimization(
                gaps=missing_skills,
                jd_text=jd_text,
                domain_analysis=domain_analysis
            ),
            "seniority_alignment": explainer.generate_seniority_alignment(
                years_experience=seniority_analysis["years_experience"],
                required_years=seniority_analysis["required_years"],
                your_level=seniority_analysis["your_level"],
                required_level=seniority_analysis["required_level"],
                gap=seniority_analysis["gap"],
                domain_analysis=domain_analysis
            )
        }
        
        if missing_skills and overall_score < 95:
            coros["roadmap"] = explainer.generate_roadmap(missing_skills, gap_type)
            
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
            
        # Run all generators in parallel
        keys = list(coros.keys())
        results = await asyncio.gather(*coros.values())
        
        # Cancel the updater once generation finishes
        updater_task.cancel()
        
        phase3_results = dict(zip(keys, results))
        
        executive_summary = phase3_results["executive_summary"]
        ats_optimization = phase3_results["ats_optimization"]
        seniority_alignment = phase3_results["seniority_alignment"]
        roadmap = phase3_results.get("roadmap", None)
        
        await report(85, "")
        from app.utils.logger import logger
        if roadmap:
            logger.info("🔗 Validating and processing roadmap links...")
            roadmap = await self.link_processor.process_response(roadmap)
            
        if ats_optimization:
            logger.info("🔗 Validating ATS optimization links...")
            ats_optimization = await self.link_processor.process_response(ats_optimization)
            
        if seniority_alignment:
            logger.info("🔗 Validating seniority alignment links...")
            seniority_alignment = await self.link_processor.process_response(seniority_alignment)
            
        logger.info("✅ Link processing complete")
        
        # Merge AI-generated seniority alignment back into the deterministic seniority_analysis dictionary
        seniority_analysis.update(seniority_alignment)
            
        # Build raw payload
        raw_payload = {
            "id": f"ai-{uuid.uuid4().hex[:8]}",
            "skills_detected": skills_detected,
            "low_confidence": low_confidence,
            "executive_summary": executive_summary,
            "overall_score": overall_score,
            "score_breakdown": {
                "skills_match": skills_score,
                "seniority_match": seniority_analysis["seniority_score"],
                "domain_match": 100 if domain_analysis["domain_match"] else 0
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
            "friction_points": friction_data["friction_points"],
            "strengths": friction_data["strengths"],
            "skill_gaps": friction_data["skill_gaps"],
            "ats_optimization": ats_optimization,
            "roadmap": roadmap
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
