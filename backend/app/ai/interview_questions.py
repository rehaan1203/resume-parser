"""Generate interview questions based on resume and JD."""
from typing import List, Dict, Any
from app.ai.client import GenAIClient
from app.prompts.career_prompt import INTERVIEW_QUESTIONS_PROMPT
from app.utils.logger import logger

class InterviewQuestionGenerator:
    """Generate interview questions based on resume-JD analysis."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
    
    async def generate_questions(
        self,
        resume: str,
        jd: str,
        skill_gaps: List[str],
        strengths: List[str],
        num_questions: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate interview questions."""
        try:
            prompt = INTERVIEW_QUESTIONS_PROMPT.format(
                resume=resume[:2000],
                jd=jd[:2000],
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
            return questions
            
        except Exception as e:
            logger.error(f"Interview question generation failed: {e}")
            return self._get_default_questions(skill_gaps)
    
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
