"""HyDE (Hypothetical Document Embeddings) Query Expander.

Synthesizes rich, domain-dense hypothetical course syllabi and competency descriptions
for brief skill gap keywords, dramatically increasing semantic density and cosine
similarity against authoritative catalog resource vectors.
"""
import os
import re
from typing import Dict, Optional
from app.knowledge.models import HyDEQuery
from app.utils.logger import logger
from app.config import settings

# Curated high-density hypothetical syllabi for instant 0ms deterministic expansion
DETERMINISTIC_SYLLABI: Dict[str, str] = {
    # Tech / Cloud / DevOps
    "kubernetes": "Complete curriculum on container orchestration with Kubernetes: Pod lifecycle, multi-container pods, Deployments, ReplicaSets, ClusterIP and NodePort Services, Ingress controllers, PersistentVolumes, ConfigMaps, Secrets, Helm chart packaging, and cluster scaling.",
    "docker": "Comprehensive hands-on training in containerization with Docker: writing efficient Dockerfiles, multi-stage image builds, volume persistence, bridge networking, Docker Compose orchestration for multi-container web apps, and container security best practices.",
    "aws": "Enterprise cloud architecture on Amazon Web Services (AWS): VPC subnets, route tables, internet gateways, EC2 compute sizing, Auto Scaling, S3 bucket policies, RDS PostgreSQL databases, IAM roles, security groups, CloudWatch telemetry, and high availability design.",
    "terraform": "Infrastructure as Code (IaC) engineering with HashiCorp Terraform: HCL syntax, provider configurations, resource declarations, module design, remote state locking with S3 and DynamoDB, terraform plan validation, drift mitigation, and CI/CD pipelines.",
    "python": "Mastery of Python software development: object-oriented design, functional paradigms, list and dictionary comprehensions, generator functions, asynchronous programming with asyncio, unit testing with pytest, packaging, and clean code principles.",
    "fastapi": "Building high-performance asynchronous microservices with FastAPI: Pydantic schema validation, dependency injection, async database connections, OAuth2 JWT authentication, background tasks, Swagger documentation, and Docker container deployment.",
    "machine_learning": "Statistical machine learning fundamentals using Python and Scikit-Learn: supervised regression and classification, decision trees, random forests, gradient boosting (XGBoost), unsupervised K-means clustering, PCA dimensionality reduction, and cross-validation.",
    "pytorch": "Deep learning engineering with PyTorch: computational graphs, automatic differentiation with autograd, building convolutional neural networks (CNNs), recurrent neural networks (RNNs), attention mechanisms, Transformer architectures, and GPU training.",
    "mlops": "Production Machine Learning Operations (MLOps): experiment tracking with MLflow, dataset versioning, model registry workflows, automated CI/CD retraining pipelines, high-throughput model serving with FastAPI/Triton, latency monitoring, and data drift detection.",
    "linux": "Linux system administration fundamentals: Bash shell commands, user and group management, file permissions (chmod/chown), process monitoring (top/ps), systemd service management, package managers (apt/yum), networking tools (netstat/curl), and SSH configuration.",

    # Finance
    "financial_modeling": "Corporate financial modeling mastery: dynamic three-statement integration (Income Statement, Balance Sheet, Cash Flow), working capital schedules, depreciation waterfalls, interest circularity resolution, and scenario sensitivity tables.",
    "dcf_valuation": "Discounted Cash Flow (DCF) valuation: forecasting unlevered free cash flows, calculating Weighted Average Cost of Capital (WACC), capital asset pricing model (CAPM), beta unlevering, terminal value via Gordon Growth and EV/EBITDA exit multiples.",
    "accounting": "Financial accounting principles under US GAAP and IFRS: revenue recognition rules, accrual vs cash accounting, capitalizing vs expensing assets, inventory accounting (FIFO/LIFO), debt amortization, and financial statement ratio analysis.",
    "risk_management": "Enterprise quantitative risk management: Value at Risk (VaR) calculation, stress testing, Monte Carlo simulations, interest rate risk, liquidity ratios, credit risk default modeling, and Basel regulatory capital frameworks.",

    # Healthcare
    "hipaa": "Comprehensive HIPAA compliance and health information security: Privacy Rule standards for Protected Health Information (PHI), Security Rule administrative, physical, and technical safeguards, Business Associate Agreements (BAAs), and breach protocol.",
    "ehr": "Electronic Health Record (EHR) system configuration and clinical documentation: Epic/Cerner charting workflows, order sets, clinical decision support alerts, medication reconciliation, and user acceptance testing in clinical environments.",
    "hl7": "Healthcare data interoperability and integration engineering: HL7 v2 ADT/ORM/ORU message parsing, segment structure, MLLP transmission protocols, and interface engine configuration (Mirth Connect/Rhapsody).",
    "fhir": "HL7 FHIR RESTful healthcare architecture: Patient, Observation, Condition, and Encounter resource schemas, JSON representations, SMART on FHIR app authorization, FHIR search parameters, and clinical data interoperability.",

    # Legal
    "contract_law": "Commercial contract drafting and review: indemnification clauses, representations and warranties, limitation of liability, intellectual property assignments, termination conditions, dispute resolution mechanisms, and breach of contract remedies.",
    "gdpr": "Global data protection and privacy regulation: General Data Protection Regulation (GDPR) lawful bases, Data Protection Impact Assessments (DPIAs), cross-border data transfer mechanisms (SCCs), data subject rights, and privacy by design controls.",
    "patent_law": "Patent prosecution and intellectual property protection: USPTO patent application drafting, patentability requirements (novelty and non-obviousness), independent and dependent claim construction, prior art searching, and office action responses.",

    # Trades
    "plc_programming": "Industrial automation with Programmable Logic Controllers (PLC): ladder logic programming, digital and analog I/O wiring, timers, counters, relay logic, variable frequency drive (VFD) integration, and troubleshooting commercial motor controls.",
    "bacnet": "Building Automation Systems (BAS) and BACnet communication protocols: BACnet MS/TP and IP network topology, device addressing, analog/binary input/output object mapping, Direct Digital Controls (DDC), and HVAC scheduling."
}

class HyDEExpander:
    """Expands concise skill queries into rich hypothetical syllabi."""

    def __init__(self, client=None):
        self.client = client
        self.enabled = getattr(settings, "rag_enable_hyde", True)

    def _normalize_key(self, skill: str) -> str:
        """Normalize skill string to canonical key for lookup."""
        return re.sub(r"[^a-z0-9]", "_", skill.strip().lower()).strip("_")

    async def expand(self, skill: str, domain: Optional[str] = None) -> HyDEQuery:
        """
        Generate a dense hypothetical document for a given skill gap.
        Uses deterministic syllabus dictionary first for 0ms latency;
        falls back to structured synthesis if not in catalog.
        """
        clean_skill = skill.strip()
        norm_key = self._normalize_key(clean_skill)

        # 1. Check deterministic library
        for key, syllabus in DETERMINISTIC_SYLLABI.items():
            if key in norm_key or norm_key in key:
                logger.debug(f"HyDE: Exact syllabus match for '{skill}' -> '{key}'")
                return HyDEQuery(
                    skill=clean_skill,
                    domain=domain or "tech",
                    hypothetical_curriculum=syllabus,
                    is_fallback=False
                )

        # 2. LLM Expansion (if client available and enabled)
        if self.client and hasattr(self.client, "generate_content"):
            try:
                prompt = (
                    f"Write a concise 2-sentence technical syllabus description for an authoritative "
                    f"professional course teaching '{clean_skill}' in the '{domain or 'technology'}' field. "
                    f"Include core modules, tools, frameworks, and practical skills covered."
                )
                generated = await self.client.generate_content(prompt)
                if generated and len(generated.strip()) > 30:
                    return HyDEQuery(
                        skill=clean_skill,
                        domain=domain or "tech",
                        hypothetical_curriculum=generated.strip(),
                        is_fallback=False
                    )
            except Exception as e:
                logger.debug(f"HyDE LLM generation error: {e}")

        # 3. Deterministic synthetic template fallback (zero external calls)
        fallback_curriculum = (
            f"Comprehensive professional curriculum and hands-on laboratory exercises for {clean_skill}: "
            f"covering fundamental architecture, core industry tools, best practices, implementation patterns, "
            f"and applied problem solving in {domain or 'modern industry'}."
        )
        return HyDEQuery(
            skill=clean_skill,
            domain=domain or "tech",
            hypothetical_curriculum=fallback_curriculum,
            is_fallback=True
        )

_EXPANDER_SINGLETON: Optional[HyDEExpander] = None

def get_hyde_expander(client=None) -> HyDEExpander:
    """Singleton getter for HyDEExpander."""
    global _EXPANDER_SINGLETON
    if _EXPANDER_SINGLETON is None:
        _EXPANDER_SINGLETON = HyDEExpander(client=client)
    return _EXPANDER_SINGLETON

