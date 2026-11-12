"""Generate interview questions based on resume, JD, and RAG interview rubrics."""
from typing import List, Dict, Any, Optional
from app.ai.client import GenAIClient
from app.prompts.career_prompt import INTERVIEW_QUESTIONS_PROMPT
from app.knowledge.retriever import get_retriever
from app.utils.document_chunker import extract_core_sections
from app.utils.logger import logger

class InterviewQuestionGenerator:
    """Generate interview questions based on resume-JD analysis and verified STAR rubrics."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
        self.is_fallback = False
    
    async def generate_questions(
        self,
        resume: str,
        jd: str,
        skill_gaps: List[str],
        strengths: List[str],
        num_questions: int = 10,
        domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate interview questions grounded in verified evaluation criteria."""
        # Retrieve curated interview guide rubrics from knowledge base
        curated_guides = []
        try:
            retriever = get_retriever()
            curated_guides = retriever.get_interview_guides_for_skills(
                skills=skill_gaps,
                domain=domain,
                limit=3
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve interview guides from RAG: {e}")

        try:
            self.is_fallback = False
            prompt = INTERVIEW_QUESTIONS_PROMPT.format(
                resume=extract_core_sections(resume, doc_type="resume", max_chars=4000),
                jd=extract_core_sections(jd, doc_type="jd", max_chars=4000),
                skill_gaps=", ".join(skill_gaps[:5]),
                strengths=", ".join(strengths[:3]),
                num_questions=num_questions
            )
            
            schema = {
                "questions": [
                    {
                        "category": "technical|behavioral|situational",
                        "question": "string",
                        "expected_answer": "string",
                        "hint": "string",
                        "difficulty": "easy|medium|hard"
                    }
                ]
            }
            
            result = await self.client.generate_structured_content(prompt, schema)
            questions = result.get("questions", [])
            logger.info(f"Generated {len(questions)} interview questions")

            # Semantically attach verified hiring rubrics & STAR exemplar answers by skill focus
            self._attach_curated_guides(questions, curated_guides)
            return questions
            
        except Exception as e:
            logger.error(f"Interview question generation failed: {e}")
            self.is_fallback = True
            fallback_qs = self._get_default_questions(skill_gaps)
            self._attach_curated_guides(fallback_qs, curated_guides)
            return fallback_qs

    def _attach_curated_guides(self, questions: List[Dict[str, Any]], curated_guides: List[Any]):
        """Attach verified rubrics and STAR exemplars to matching questions by semantic skill focus."""
        if not curated_guides or not questions:
            return

        used_guides = set()
        for q in questions:
            q_text = (q.get("question", "") + " " + q.get("hint", "") + " " + q.get("expected_answer", "")).lower()
            for guide in curated_guides:
                if guide.id in used_guides:
                    continue
                focus = guide.skill_focus.lower()
                tokens = [t.strip(",.:;()") for t in focus.split() if len(t.strip(",.:;()")) >= 2]
                if focus in q_text or any(token in q_text for token in tokens):
                    q["evaluation_criteria"] = guide.evaluation_criteria
                    q["star_model_answer"] = guide.star_model_answer.model_dump()
                    q["verified_skill_focus"] = guide.skill_focus
                    used_guides.add(guide.id)
                    break

        # Fallback: attach any remaining unmatched guides only to technical questions
        unmatched_guides = [g for g in curated_guides if g.id not in used_guides]
        for q in questions:
            if not unmatched_guides:
                break
            if "star_model_answer" not in q and q.get("category") != "behavioral":
                guide = unmatched_guides.pop(0)
                q["evaluation_criteria"] = guide.evaluation_criteria
                q["star_model_answer"] = guide.star_model_answer.model_dump()
                q["verified_skill_focus"] = guide.skill_focus
    
    def _get_default_questions(self, skill_gaps: List[str]) -> List[Dict[str, Any]]:
        """Get default questions if AI fails."""
        questions = []
        for gap in skill_gaps[:3]:
            questions.append({
                "category": "technical",
                "question": f"Describe your experience with {gap}",
                "expected_answer": f"Detailed experience with {gap} including projects and challenges",
                "hint": f"Focus on {gap} projects and problem-solving",
                "difficulty": "medium"
            })
        
        questions.append({
            "category": "behavioral",
            "question": "Tell me about a challenging project you worked on",
            "expected_answer": "Description of project, challenges, and solutions",
            "hint": "Use STAR method",
            "difficulty": "medium"
        })
        
        return questions
