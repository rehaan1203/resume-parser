"""Keyword-based deterministic domain detection."""
import re
from typing import Dict, Any

DOMAIN_KEYWORDS = {
    "software_engineering": ["software", "developer", "engineer", "programming", "python", "java", "react", "node", "frontend", "backend"],
    "data_science": [
        "data", "machine learning", "ml", "ai", "artificial intelligence", "deep learning",
        "llm", "llms", "neural", "nlp", "analytics", "sql", "pandas", "data science",
        "pytorch", "tensorflow", "model training", "transformer", "transformers"
    ],
    "legal": ["law", "legal", "attorney", "paralegal", "counsel", "litigation", "contract", "contracts"],
    "finance": ["finance", "accounting", "banking", "investment", "financial", "cpa", "audit"],
    "marketing": ["marketing", "seo", "content", "social media", "campaign", "digital marketing"],
    "sales": ["sales", "account executive", "business development", "b2b", "revenue"],
    "hr": ["hr", "human resources", "recruitment", "talent acquisition", "onboarding"],
    "product": ["product manager", "roadmap", "agile", "scrum", "product owner"],
    "healthcare": ["nurse", "nursing", "clinical", "hospital", "patient", "medical", "healthcare", "icu", "bls", "acls", "rn", "physician", "doctor"],
    "trades": ["hvac", "electrician", "plumbing", "machinist", "technician", "cnc", "welder", "mechanical", "electrical", "refrigeration"]
}

# Domains with strong technical or functional affinity that represent viable career transitions
COMPATIBLE_DOMAINS = {
    "software_engineering": {"data_science", "product"},
    "data_science": {"software_engineering", "product"},
    "product": {"software_engineering", "data_science", "marketing"},
    "marketing": {"sales", "product"},
    "sales": {"marketing"},
    "finance": {"hr"},
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
    """Analyze domain match between resume and JD, supporting compatible career transitions."""
    resume_domain = detect_domain(resume_text)
    jd_domain = detect_domain(jd_text)
    
    is_exact_match = (resume_domain == jd_domain) or ("unknown" in (resume_domain, jd_domain))
    is_compatible = (
        is_exact_match or 
        (resume_domain in COMPATIBLE_DOMAINS and jd_domain in COMPATIBLE_DOMAINS.get(resume_domain, set()))
    )
    is_transition = is_compatible and not is_exact_match
    
    return {
        "resume_domain": resume_domain,
        "jd_domain": jd_domain,
        "domain_match": is_compatible,
        "is_exact_match": is_exact_match,
        "is_compatible_transition": is_transition,
    }
