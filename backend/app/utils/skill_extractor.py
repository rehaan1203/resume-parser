"""Keyword-based deterministic skill extraction."""
import re
from typing import List, Dict, Any, Tuple

# A basic comprehensive skill list for deterministic extraction
COMMON_SKILLS = [
    "python", "java", "javascript", "react", "node", "sql", "aws", "azure", "docker", "kubernetes",
    "git", "agile", "scrum", "machine learning", "data analysis", "project management",
    "html", "css", "typescript", "c++", "c#", "ruby", "go", "rust", "php",
    "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn",
    "contract drafting", "legal research", "technology law", "data privacy", "litigation", "compliance",
    "seo", "content marketing", "social media marketing", "google analytics",
    "b2b sales", "account management", "crm", "salesforce"
]

def extract_skills(text: str) -> List[str]:
    """Extract skills deterministically based on keyword matching."""
    if not text:
        return []
        
    text_lower = text.lower()
    extracted = []
    
    for skill in COMMON_SKILLS:
        # Use regex to find whole word matches
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            # Format nicely (Title Case, except for short acronyms like AWS, SQL)
            formatted = skill.upper() if len(skill) <= 3 else skill.title()
            extracted.append(formatted)
            
    return sorted(list(set(extracted)))

def compare_skills(resume_skills: List[str], jd_skills: List[str]) -> Tuple[List[str], List[str]]:
    """Compare resume and JD skills to find matches and gaps."""
    resume_set = set(s.lower() for s in resume_skills)
    
    matching = []
    missing = []
    
    for skill in jd_skills:
        if skill.lower() in resume_set:
            matching.append(skill)
        else:
            missing.append(skill)
            
    return matching, missing
