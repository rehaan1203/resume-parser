"""Comprehensive domain detection for ALL domains with deterministic results."""
import re
from typing import List, Dict, Any, Optional
from app.models.domain_models import Domain, DomainDetectionResult
from app.utils.logger import logger

class DomainDetector:
    """Detects domain from text with deterministic results."""

    # Comprehensive domain keyword mappings - DETERMINISTIC
    DOMAIN_KEYWORDS = {
        Domain.LEGAL: {
            "keywords": [
                "law", "legal", "lawyer", "attorney", "juris doctor", "j.d.",
                "contract", "litigation", "compliance", "bar admission",
                "legal research", "legal documentation", "court filings",
                "corporate law", "civil litigation", "legal writing",
                "client representation", "negotiation", "case management",
                "affidavit", "deposition", "statute", "regulation",
                "legal opinion", "memorandum", "settlement", "mediation",
                "arbitration", "due diligence", "intellectual property",
                "technology law", "data privacy", "saas agreements"
            ],
            "related_domains": [Domain.UNKNOWN]
        },
        Domain.HEALTHCARE: {
            "keywords": [
                "medical", "patient", "clinical", "hospital", "health",
                "nursing", "doctor", "surgeon", "healthcare administration",
                "diagnosis", "treatment", "prescription", "surgery",
                "emergency", "pharmacy", "radiology", "laboratory",
                "medical research", "public health", "epidemiology",
                "health policy", "patient care", "medical records",
                "biomedical", "pharmaceutical", "clinical trials"
            ],
            "related_domains": []
        },
        Domain.FINANCE: {
            "keywords": [
                "financial", "investment", "banking", "trading", "portfolio",
                "accounting", "audit", "risk", "capital", "equity",
                "financial analysis", "financial modeling", "valuation",
                "mergers", "acquisitions", "derivatives", "bonds",
                "stocks", "commodities", "insurance", "actuary",
                "wealth management", "financial planning", "corporate finance"
            ],
            "related_domains": []
        },
        Domain.ARCHITECTURE: {
            "keywords": [
                "architect", "building", "construction", "revit", "autocad",
                "floor plan", "structural", "architectural design",
                "urban planning", "sustainable design", "interior design",
                "landscape architecture", "building codes", "zoning",
                "sketchup", "rhino", "lumion", "v-ray",
                "construction documentation", "bim", "cad"
            ],
            "related_domains": []
        },
        Domain.EDUCATION: {
            "keywords": [
                "teaching", "curriculum", "classroom", "pedagogy", "instruction",
                "academic", "lecturer", "professor", "educator",
                "lesson planning", "student assessment", "educational technology",
                "distance learning", "special education", "educational research",
                "curriculum development", "instructional design", "k-12",
                "higher education", "educational leadership", "student counseling"
            ],
            "related_domains": []
        },
        Domain.AI_ML: {
            "keywords": [
                "machine learning", "neural network", "llm", "pytorch", "tensorflow",
                "generative ai", "rag", "deep learning", "nlp", "computer vision",
                "artificial intelligence", "data science", "natural language processing",
                "transformers", "model training", "inference", "embeddings",
                "vector database", "prompt engineering", "langchain",
                "hugging face", "keras", "scikit-learn", "jupyter",
                "python", "fastapi", "docker", "kubernetes"
            ],
            "related_domains": []
        },
        Domain.SOFTWARE: {
            "keywords": [
                "software engineering", "web development", "api", "microservices",
                "backend", "frontend", "full stack", "mobile development",
                "react", "angular", "node.js", "python", "java", "c++",
                "devops", "ci/cd", "docker", "kubernetes", "aws",
                "git", "github", "rest api", "database", "sql",
                "agile", "scrum", "software architecture"
            ],
            "related_domains": []
        },
        Domain.DESIGN: {
            "keywords": [
                "ui/ux", "graphic design", "product design", "user experience",
                "visual design", "creative", "design thinking", "wireframe",
                "prototype", "figma", "sketch", "adobe", "photoshop",
                "illustrator", "invision", "design systems", "user research",
                "interaction design", "service design", "brand identity"
            ],
            "related_domains": []
        },
        Domain.MARKETING: {
            "keywords": [
                "digital marketing", "seo", "content", "social media",
                "branding", "advertising", "ppc", "email marketing",
                "marketing strategy", "market research", "analytics",
                "google analytics", "content strategy", "copywriting",
                "product marketing", "brand management", "public relations"
            ],
            "related_domains": []
        },
        Domain.SALES: {
            "keywords": [
                "business development", "account management", "sales strategy",
                "lead generation", "client acquisition", "salesforce",
                "customer relationship", "negotiation", "cold calling",
                "sales forecasting", "territory management", "enterprise sales",
                "saas sales", "sales operations", "key account management"
            ],
            "related_domains": []
        },
        Domain.HR: {
            "keywords": [
                "recruitment", "talent acquisition", "employee relations",
                "training", "performance management", "hr operations",
                "organizational development", "people operations", "compensation",
                "benefits", "employee engagement", "hr strategy",
                "workforce planning", "diversity", "onboarding", "hr analytics"
            ],
            "related_domains": []
        },
        Domain.OPERATIONS: {
            "keywords": [
                "supply chain", "logistics", "project management",
                "process improvement", "strategy", "business administration",
                "operations management", "inventory management", "procurement",
                "lean six sigma", "quality assurance", "process optimization",
                "agile methodology", "scrum master", "product manager",
                "business operations", "vendor management"
            ],
            "related_domains": []
        },
        Domain.ENGINEERING: {
            "keywords": [
                "mechanical", "electrical", "civil", "chemical", "manufacturing",
                "quality assurance", "industrial design", "materials science",
                "thermodynamics", "fluid mechanics", "structural engineering",
                "control systems", "robotics", "automation", "cad",
                "solidworks", "ansys", "matlab", "simulink"
            ],
            "related_domains": []
        },
        Domain.SCIENCE: {
            "keywords": [
                "research", "laboratory", "biology", "chemistry", "physics",
                "experimentation", "scientific research", "data analysis",
                "statistics", "bioinformatics", "genomics", "microbiology",
                "environmental science", "chemistry", "physics", "astronomy",
                "geology", "marine biology", "neuroscience", "psychology"
            ],
            "related_domains": []
        }
    }

    # Domain mapping for related domains
    RELATED_DOMAINS = {
        Domain.LEGAL: [Domain.UNKNOWN],
        Domain.HEALTHCARE: [Domain.SCIENCE, Domain.UNKNOWN],
        Domain.FINANCE: [Domain.OPERATIONS, Domain.UNKNOWN],
        Domain.ARCHITECTURE: [Domain.ENGINEERING, Domain.DESIGN, Domain.UNKNOWN],
        Domain.EDUCATION: [Domain.HR, Domain.UNKNOWN],
        Domain.AI_ML: [Domain.SOFTWARE, Domain.SCIENCE, Domain.UNKNOWN],
        Domain.SOFTWARE: [Domain.AI_ML, Domain.DESIGN, Domain.UNKNOWN],
        Domain.DESIGN: [Domain.MARKETING, Domain.UNKNOWN],
        Domain.MARKETING: [Domain.DESIGN, Domain.SALES, Domain.UNKNOWN],
        Domain.SALES: [Domain.MARKETING, Domain.UNKNOWN],
        Domain.HR: [Domain.EDUCATION, Domain.OPERATIONS, Domain.UNKNOWN],
        Domain.OPERATIONS: [Domain.FINANCE, Domain.HR, Domain.UNKNOWN],
        Domain.ENGINEERING: [Domain.ARCHITECTURE, Domain.SCIENCE, Domain.UNKNOWN],
        Domain.SCIENCE: [Domain.HEALTHCARE, Domain.ENGINEERING, Domain.UNKNOWN]
    }

    def __init__(self):
        self.domain_keywords = self.DOMAIN_KEYWORDS
        self.related_domains = self.RELATED_DOMAINS

    async def detect(self, text: str) -> DomainDetectionResult:
        """Detect domain from text with deterministic results."""
        if not text:
            return DomainDetectionResult(
                domain=Domain.UNKNOWN,
                confidence=0,
                evidence=[],
                reasoning="No text provided"
            )

        text_lower = text.lower()
        domain_scores = {}

        # Score each domain
        for domain, data in self.domain_keywords.items():
            score = 0
            evidence = []
            for keyword in data["keywords"]:
                if keyword.lower() in text_lower:
                    score += 1
                    evidence.append(keyword)

            domain_scores[domain] = {
                "score": score,
                "evidence": evidence[:10]  # Keep top 10 evidence
            }

        # Find highest scoring domain - DETERMINISTIC
        best_domain = Domain.UNKNOWN
        best_score = 0
        best_evidence = []

        for domain, data in domain_scores.items():
            if data["score"] > best_score:
                best_score = data["score"]
                best_domain = domain
                best_evidence = data["evidence"]

        # Calculate confidence based on raw matches rather than percentage of dictionary
        if best_score >= 3:
            confidence = 95
        elif best_score == 2:
            confidence = 75
        elif best_score == 1:
            confidence = 50
        else:
            confidence = 0

        # If confidence is low, mark as unknown
        if confidence == 0:
            best_domain = Domain.UNKNOWN
            best_evidence = []

        logger.info(f"Domain detected: {best_domain.value} (confidence: {confidence}%)")

        return DomainDetectionResult(
            domain=best_domain,
            confidence=confidence,
            evidence=best_evidence,
            reasoning=f"Detected based on {len(best_evidence)} keywords: {', '.join(best_evidence[:5])}"
        )

    def get_related_domains(self, domain: Domain) -> List[Domain]:
        """Get related domains for a given domain."""
        return self.related_domains.get(domain, [])
