"""Keyword-based deterministic domain detection."""
import re
from typing import Dict, Any

DOMAIN_KEYWORDS = {
    "software_engineering": ["software", "developer", "engineer", "programming", "python", "java", "react", "node", "frontend", "backend"],
    "data_science": ["data", "machine learning", "ai", "artificial intelligence", "analytics", "sql", "pandas", "data science"],
    "legal": ["law", "legal", "attorney", "paralegal", "counsel", "litigation", "contract", "contracts"],
    "finance": ["finance", "accounting", "banking", "investment", "financial", "cpa", "audit"],
    "marketing": ["marketing", "seo", "content", "social media", "campaign", "digital marketing"],
    "sales": ["sales", "account executive", "business development", "b2b", "revenue"],
    "hr": ["hr", "human resources", "recruitment", "talent acquisition", "onboarding"],
    "product": ["product manager", "roadmap", "agile", "scrum", "product owner"]
}

def detect_domain(text: str) -> str:
    """Detect domain deterministically based on keyword frequency."""
    if not text:
        return "unknown"
        
    text_lower = text.lower()
    domain_scores = {domain: 0 for domain in DOMAIN_KEYWORDS}
    
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            # Use regex to find whole word matches
            matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text_lower))
            domain_scores[domain] += matches
            
    # Find the domain with the highest score
    best_domain = max(domain_scores.items(), key=lambda x: x[1])
    
    if best_domain[1] > 0:
        return best_domain[0]
    return "unknown"

def analyze_domain(resume_text: str, jd_text: str) -> Dict[str, Any]:
    """Analyze domain match between resume and JD."""
    resume_domain = detect_domain(resume_text)
    jd_domain = detect_domain(jd_text)
    
    # Simple match logic. If either is unknown, we assume true to not penalize
    return {
        "resume_domain": resume_domain,
        "jd_domain": jd_domain,
        "domain_match": (resume_domain == jd_domain) or ("unknown" in (resume_domain, jd_domain))
    }
