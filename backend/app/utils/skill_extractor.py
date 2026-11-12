"""Keyword-based deterministic skill extraction."""
import re
from typing import List, Dict, Any, Tuple

# Original common skills for legacy deterministic orchestrator
COMMON_SKILLS = [
    "python", "java", "javascript", "react", "node", "sql", "aws", "azure", "docker", "kubernetes",
    "git", "agile", "scrum", "machine learning", "data analysis", "project management",
    "html", "css", "typescript", "c++", "c#", "ruby", "go", "rust", "php",
    "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn",
    "contract drafting", "legal research", "technology law", "data privacy", "litigation", "compliance",
    "seo", "content marketing", "social media marketing", "google analytics",
    "b2b sales", "account management", "crm", "salesforce"
]

# Extended multi-domain skills for OpenDomainExtractor (D4)
OPEN_DOMAIN_SKILLS = COMMON_SKILLS + [
    # Healthcare & Clinical Nursing
    "nursing", "patient care", "bls", "acls", "cpr", "icu", "telemetry", "med-surg",
    "vital signs", "phlebotomy", "triage", "ehr", "hipaa", "iv therapy",
    "clinical documentation", "infection control", "medication administration", "pediatrics", "oncology",
    # Skilled Trades & Engineering Maintenance
    "hvac", "refrigeration", "epa 608", "electrical wiring", "blueprints",
    "schematics", "plumbing", "welding", "cnc machining", "preventative maintenance", "osha",
    "soldering", "pneumatics", "hydraulics", "circuit analysis",
    # Architecture & Construction Design
    "revit", "autocad", "bim", "building codes",
    "construction documentation", "sketchup",
    # Legal & Corporate Compliance
    "contract review", "regulatory compliance", "due diligence", "corporate governance", "intellectual property",
    # Finance & Accounting
    "financial modeling", "auditing", "gaap", "tax preparation", "general ledger", "account reconciliation",
    # Education & Academia
    "curriculum development", "instruction", "classroom management", "pedagogy", "lesson planning",
    "physics", "chemistry", "stem",
    # Supply Chain & Operations
    "supply chain", "logistics", "inventory management", "procurement", "warehouse operations",
    "six sigma", "warehouse management", "wms", "sap",
    # Hospitality & Services
    "hospitality", "hotel management", "guest services", "event planning", "hotel operations",
    "p&l management", "food & beverage", "opera pms",
    # Advanced Data Engineering
    "spark", "flink", "kafka", "snowflake", "scala"
]

UPPERCASE_ACRONYMS = {
    "aws", "sql", "css", "php", "seo", "crm", "git", "cpr", "bls", "acls", "icu", "ehr",
    "hipaa", "hvac", "osha", "gaap", "cnc", "b2b", "api", "rest", "bim", "sap", "wms", "pms"
}

def extract_skills(text: str) -> List[str]:
    """Extract skills deterministically based on keyword matching."""
    if not text:
        return []
        
    text_lower = text.lower()
    extracted = []
    
    for skill in COMMON_SKILLS:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            formatted = skill.upper() if len(skill) <= 3 else skill.title()
            extracted.append(formatted)
            
    return sorted(list(set(extracted)))

def extract_open_domain_skills(text: str) -> List[str]:
    """Extract skills across all domains for OpenDomainExtractor."""
    if not text:
        return []

    text_lower = text.lower()
    extracted = []

    for skill in OPEN_DOMAIN_SKILLS:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            if skill.lower() in UPPERCASE_ACRONYMS or len(skill) <= 3:
                formatted = skill.upper()
            else:
                formatted = skill.title()
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
