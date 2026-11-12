"""Comprehensive regression and end-to-end scenario tests for prompt grounding, RAG isolation, link disambiguation, and client resilience."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest

from app.ai.client import GenAIClient
from app.ai.explainer import Phase3Explainer
from app.ai.interview_questions import InterviewQuestionGenerator
from app.ai.career_advisor import CareerAdvisor
from app.ai.orchestrator import DeterministicOrchestrator
from app.config import settings
from app.knowledge.crag_evaluator import CRAGEvaluator
from app.knowledge.models import VerifiedResource, ResourceType, DifficultyLevel
from app.knowledge.retriever import KnowledgeRetriever
from app.prompts.roadmap_prompt import build_rag_upskill_roadmap_prompt
from app.services.outlook_service import OutlookService
from app.utils.exceptions import LLMTruncationError
from app.utils.link_processor import LinkProcessor
from app.utils.link_replacer import LinkReplacer

# Capture unpatched implementations before conftest.py's autouse hermetic fixture wraps them
_ORIG_PROCESS_RESPONSE = LinkProcessor.process_response
_ORIG_GENERATE_STRUCTURED = GenAIClient.generate_structured_content


# ---------------------------------------------------------------------------
# 1. Prompt Grounding & Verdict Consistency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_holistic_prompt_compatible_domain_forbids_mismatch_and_uses_placeholders():
    explainer = Phase3Explainer()
    captured = {}

    async def fake_structured(prompt, output_schema, **kwargs):
        captured["prompt"] = prompt
        return {
            "executive_summary": "Candidate achieved 51% with compatible transition into AI Engineering.",
            "ats_optimization": {"keywords": ["Azure OpenAI"], "phrasing": [], "formatting_tips": []},
            "seniority_alignment": {"summary": "Minor 1.7 yr gap.", "recommendation": "Target junior roles.", "next_steps": ["Ship RAG apps"]},
        }

    explainer.client.generate_structured_content = fake_structured
    await explainer.generate_holistic_insights(
        score=51,
        strengths=["Python", "REST APIs", "SQL"],
        gaps=["Azure Blob Storage", "Azure Security", "LangGraph"],
        years_experience=1.3,
        required_years=3,
        your_level="Entry",
        required_level="Mid",
        seniority_gap=1.7,
        domain_analysis={
            "resume_domain": "software_engineering",
            "jd_domain": "data_science",
            "detected_role_domain": "AI Engineering",
            "domain_match": True,
            "is_exact_match": False,
            "is_compatible_transition": True,
            "is_mismatch": False,
        },
        resume_excerpt="- Built FastAPI REST services for document ingestion workflows\n- Wrote PostgreSQL analytics queries",
    )

    prompt = captured["prompt"]
    assert "85% Domain Match" in prompt
    assert "AI Engineering" in prompt
    assert "NEVER write 'domain mismatch'" in prompt
    assert "CANDIDATE RESUME EXCERPT" in prompt
    assert "Built FastAPI REST services" in prompt
    assert "[X]%" in prompt


@pytest.mark.asyncio
async def test_holistic_prompt_true_mismatch_and_exact_match_variants():
    explainer = Phase3Explainer()
    prompts = []

    async def fake_structured(prompt, output_schema, **kwargs):
        prompts.append(prompt)
        return {"executive_summary": "ok", "ats_optimization": {}, "seniority_alignment": {}}

    explainer.client.generate_structured_content = fake_structured

    # True mismatch
    await explainer.generate_holistic_insights(
        score=15,
        strengths=["Contract Review"],
        gaps=["Python", "PyTorch"],
        years_experience=5,
        required_years=3,
        your_level="Senior",
        required_level="Mid",
        seniority_gap=0,
        domain_analysis={
            "resume_domain": "legal",
            "jd_domain": "data_science",
            "domain_match": False,
            "is_exact_match": False,
            "is_compatible_transition": False,
            "is_mismatch": True,
        },
    )
    assert "Significant domain shift from Legal to Data Science" in prompts[-1]

    # Exact match
    await explainer.generate_holistic_insights(
        score=88,
        strengths=["Python", "Azure OpenAI"],
        gaps=["LangGraph"],
        years_experience=3,
        required_years=3,
        your_level="Mid",
        required_level="Mid",
        seniority_gap=0,
        domain_analysis={
            "resume_domain": "data_science",
            "jd_domain": "data_science",
            "detected_role_domain": "AI Engineering",
            "domain_match": True,
            "is_exact_match": True,
            "is_compatible_transition": False,
            "is_mismatch": False,
        },
    )
    assert "100% Domain Match" in prompts[-1]
    assert "Do NOT state there is a domain mismatch" in prompts[-1]


def test_rag_roadmap_prompt_retains_8_resources_and_ecosystem_guard():
    resources = [
        {"title": f"Azure Resource {i}", "url": f"https://learn.microsoft.com/en-us/azure/r{i}", "type": "documentation", "description": "Official Azure guide."}
        for i in range(8)
    ]
    prompt = build_rag_upskill_roadmap_prompt(
        gaps=["Azure Blob Storage", "Azure Security", "Azure Monitoring", "Azure OpenAI", "LangGraph"],
        gap_type="short_upskill",
        verified_resources=resources,
        target_role="AI Engineer",
    )
    assert "targeting 'AI Engineer'" in prompt
    assert "Azure Resource 7" in prompt  # Up to 8 verified resources preserved
    assert "NEVER introduce competing cloud vendors" in prompt


# ---------------------------------------------------------------------------
# 2. RAG Knowledge Base Cross-Cloud Vendor Isolation & CRAG
# ---------------------------------------------------------------------------

def test_crag_rejects_cross_cloud_vendor_conflict():
    crag = CRAGEvaluator()
    aws_resource = VerifiedResource(
        id="tech-aws-cloud-practitioner",
        title="AWS Cloud Practitioner Essentials",
        url="https://explore.skillbuilder.aws/learn/course/external/view/elearning/134/aws-cloud-practitioner-essentials",
        platform="AWS Skill Builder",
        type=ResourceType.COURSE,
        domain="tech",
        skills_covered=["aws", "cloud computing", "cloud architecture", "ec2", "s3"],
        difficulty=DifficultyLevel.BEGINNER,
        description="Official foundational overview of AWS Cloud concepts.",
    )
    azure_resource = VerifiedResource(
        id="tech-azure-security-defender",
        title="Microsoft Azure Security Fundamentals & Defender for Cloud",
        url="https://learn.microsoft.com/en-us/azure/security/fundamentals/overview",
        platform="Microsoft Learn",
        type=ResourceType.DOCUMENTATION,
        domain="tech",
        skills_covered=["azure security", "microsoft defender", "rbac", "azure"],
        difficulty=DifficultyLevel.INTERMEDIATE,
        description="Official Azure security architecture overview.",
    )

    aws_grade = crag.grade_resource(aws_resource, "Azure Security", seniority="entry", domain="tech")
    assert aws_grade.grade == "incorrect"
    assert aws_grade.confidence == 0.0
    assert "mismatch" in aws_grade.reason.lower()

    azure_grade = crag.grade_resource(azure_resource, "Azure Security", seniority="entry", domain="tech")
    assert azure_grade.grade in {"correct", "ambiguous"}
    assert azure_grade.confidence >= 0.70


@pytest.mark.asyncio
async def test_retriever_returns_azure_and_langgraph_without_aws_leakage():
    retriever = KnowledgeRetriever()
    await retriever.initialize_and_index_catalogs()

    results = await retriever.search_for_gaps(
        skills=["Azure Blob Storage", "Azure Security", "Azure Monitoring", "Azure OpenAI", "LangGraph"],
        domain="tech",
        limit=8,
        seniority="Entry",
    )
    urls = [str(r.url).lower() for r in results]
    titles = [r.title.lower() for r in results]

    assert len(results) >= 4
    assert not any("skillbuilder.aws" in u or "aws cloud practitioner" in t for u, t in zip(urls, titles))
    assert any("learn.microsoft.com/en-us/azure" in u for u in urls)
    assert any("langgraph" in u for u in urls)


# ---------------------------------------------------------------------------
# 3. Link Title Disambiguation & Concurrent Replacement
# ---------------------------------------------------------------------------

def test_outlook_link_title_disambiguates_generic_overview_slugs():
    svc = OutlookService()
    monitor_title = svc._derive_readable_link_title("https://learn.microsoft.com/en-us/azure/azure-monitor/overview")
    security_title = svc._derive_readable_link_title("https://learn.microsoft.com/en-us/azure/security/fundamentals/overview")
    openai_title = svc._derive_readable_link_title("https://learn.microsoft.com/en-us/azure/ai-services/openai/overview")
    langgraph_title = svc._derive_readable_link_title("https://langchain-ai.github.io/langgraph/")

    assert monitor_title == "Microsoft Learn: Azure Monitor Overview"
    assert security_title == "Microsoft Learn: Security Fundamentals Overview"
    assert openai_title == "Microsoft Learn: OpenAI Overview"
    assert monitor_title != security_title != openai_title
    assert "LangGraph" in langgraph_title


@pytest.mark.asyncio
async def test_link_processor_concurrent_replacement_without_external_keys():
    LinkReplacer._SHARED_REPLACEMENT_CACHE.clear()
    processor = LinkProcessor()

    with patch.object(settings, "tavily_api_key", None), patch.object(settings, "youtube_api_key", None):
        processor.validator.validate_many = AsyncMock(return_value={
            "https://broken.example.com/azure-blob": {"status": "error", "status_code": 404},
            "https://broken.example.com/langgraph": {"status": "error", "status_code": 404},
            "https://fastapi.tiangolo.com/tutorial/": {"status": "ok", "status_code": 200},
        })

        payload = {
            "weeks": [
                {
                    "week": 1,
                    "days": [
                        {"day": 1, "action": "Configure Azure Blob Storage containers", "resources": ["https://broken.example.com/azure-blob"]},
                        {"day": 2, "action": "Build LangGraph agent loops", "resources": ["https://broken.example.com/langgraph"]},
                        {"day": 3, "action": "Review FastAPI routing", "resources": ["https://fastapi.tiangolo.com/tutorial/"]},
                    ],
                }
            ]
        }
        out = await _ORIG_PROCESS_RESPONSE(processor, payload)

    days = out["weeks"][0]["days"]
    assert "learn.microsoft.com/en-us/search/?terms=" in days[0]["resources"][0]
    assert days[1]["resources"][0] == "https://langchain-ai.github.io/langgraph/"
    assert days[2]["resources"][0] == "https://fastapi.tiangolo.com/tutorial/"


# ---------------------------------------------------------------------------
# 4. GenAIClient Retry Policy & Structured JSON Recovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_genai_client_does_not_retry_truncation_and_recovers_malformed_json():
    client = GenAIClient()
    calls = {"trunc": 0, "json": 0}

    # Case A: LLMTruncationError must fail fast (1 attempt, never 4x retry storm)
    async def mock_truncated(*args, **kwargs):
        calls["trunc"] += 1
        return SimpleNamespace(
            model="mistral-small-latest",
            usage=SimpleNamespace(completion_tokens=8192),
            choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content="{truncated"))],
        )

    with patch.object(client, "client", SimpleNamespace(chat=mock_truncated)):
        GenAIClient._groq_unavailable = True
        try:
            with pytest.raises(LLMTruncationError):
                await client.generate_content("Oversized prompt")
        finally:
            GenAIClient._groq_unavailable = False

    assert calls["trunc"] == 1

    # Case B: Malformed first JSON triggers 1 strict retry at temp=0.0 and recovers
    async def mock_generate_content(prompt, model=None, temperature=0.1, max_output_tokens=8192):
        calls["json"] += 1
        if calls["json"] == 1:
            return "Here is JSON: {bad json"
        assert temperature == 0.0
        return '```json\n{"status": "ok", "count": 2}\n```'

    client.generate_content = mock_generate_content
    parsed = await _ORIG_GENERATE_STRUCTURED(client, "Test", {"status": "string", "count": 0})
    assert parsed == {"status": "ok", "count": 2}
    assert calls["json"] == 2


# ---------------------------------------------------------------------------
# 5. Smart Chunking in Interview & Career Services
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interview_and_career_services_preserve_bottom_skills_past_2000_chars():
    long_filler = "Professional Summary\n" + ("Delivered enterprise software solutions across cross-functional agile teams. " * 45)
    bottom_tail = "\n\nSKILLS\nAzure OpenAI, LangGraph, Kubernetes, PostgreSQL\n\nEXPERIENCE\nAI Engineer (Aug 2025 - Present)"
    long_resume = long_filler + bottom_tail
    assert len(long_resume) > 3000

    captured = {}

    async def fake_structured(prompt, schema, **kwargs):
        captured[len(captured)] = prompt
        if "questions" in schema:
            return {"questions": []}
        return {"advice": {"short_term_goals": [], "long_term_goals": [], "skills_to_develop": [], "career_paths": [], "recommended_roles": [], "salary_expectations": {"range": "$100k", "factors": []}}}

    fake_client = SimpleNamespace(generate_structured_content=fake_structured)
    iq_gen = InterviewQuestionGenerator(fake_client)
    await iq_gen.generate_questions(long_resume, long_resume, ["Azure OpenAI"], ["Python"], domain="tech")

    advisor = CareerAdvisor(fake_client)
    await advisor.get_advice(long_resume, "1.3 years", "AI Engineer", ["Azure OpenAI"], domain="tech")

    assert "Azure OpenAI" in captured[0]
    assert "Azure OpenAI" in captured[1]


# ---------------------------------------------------------------------------
# 6. Full Orchestrator + Outlook Report End-to-End Parity Simulation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_aarav_azure_ai_parity_and_report_rendering():
    orchestrator = DeterministicOrchestrator()
    outlook = OutlookService()

    resume = (
        "Aarav Sharma\n"
        "EDUCATION\n"
        "B.Tech in Computer Science (2021 - 2025)\n"
        "EXPERIENCE\n"
        "Software Engineer Developer, CloudTech (Aug 2025 - Present)\n"
        "- Built backend REST APIs and frontend integrations with Python, Java, React, and FastAPI.\n"
        "- Managed Git workflows and containerized local software deployments.\n"
        "- Supported SQL queries and API service reliability.\n"
    )
    jd = (
        "Ai Engineer\n"
        "Requires 3+ years of AI, Machine Learning, and LLM engineering experience.\n"
        "Required Skills: Python, REST API, SQL, Git, Machine Learning, AI, Azure Blob Storage, "
        "Azure Security, Azure Monitoring, Azure OpenAI, LangGraph.\n"
    )

    mock_holistic = {
        "executive_summary": (
            "Candidate achieved a competitive technical match demonstrating Python, REST APIs, and Azure AI foundations, "
            "while needing Azure Blob Storage, Azure Security, and LangGraph along with bridging the 1.7-year seniority gap."
        ),
        "ats_optimization": {
            "keywords": ["Azure Blob Storage", "Azure Security", "Azure Monitoring", "Azure OpenAI", "LangGraph"],
            "phrasing": [
                {
                    "original": "Built REST APIs with Python and FastAPI",
                    "suggested": "Engineered asynchronous FastAPI REST APIs, improving p95 endpoint response times by [X]% across [N]+ daily requests.",
                }
            ],
            "formatting_tips": ["Place Azure AI deployment projects near top of Experience."],
        },
        "seniority_alignment": {
            "your_level": "Entry",
            "your_years": 1.3,
            "required_level": "Mid",
            "required_years": 3,
            "gap": 1.7,
            "alignment_status": "minor_gap",
            "alignment_badge": "🟡 MINOR GAP",
            "summary": "Candidate has 1.3 yrs vs 3+ yrs required.",
            "recommendation": "Target Associate/Junior AI Engineer roles while deepening Azure cloud ownership.",
            "next_steps": ["Build Azure OpenAI + LangGraph production demo"],
        },
    }
    mock_roadmap = {
        "type": "short_upskill",
        "title": "Upskill Roadmap (2 Weeks)",
        "weeks": [
            {
                "week": 1,
                "focus": "Azure Storage & Cloud Security",
                "days": [
                    {
                        "day": 1,
                        "action": "Learn Azure Blob Storage SDK and access tiers",
                        "resources": ["https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction"],
                        "estimated_time": "2 hours",
                    },
                    {
                        "day": 2,
                        "action": "Configure Azure Security RBAC and Defender",
                        "resources": ["https://learn.microsoft.com/en-us/azure/security/fundamentals/overview"],
                        "estimated_time": "2 hours",
                    },
                    {
                        "day": 3,
                        "action": "Set up Azure Monitor telemetry and LangGraph",
                        "resources": [
                            "https://learn.microsoft.com/en-us/azure/azure-monitor/overview",
                            "https://langchain-ai.github.io/langgraph/",
                        ],
                        "estimated_time": "2 hours",
                    },
                ],
            }
        ],
    }

    with (
        patch.object(settings, "orchestrator_progress_delay", 0.0),
        patch("app.ai.open_domain_extractor.OpenDomainExtractor.extract_requirements", new=AsyncMock(return_value=[])),
        patch("app.ai.explainer.Phase3Explainer.generate_holistic_insights", new=AsyncMock(return_value=mock_holistic)),
        patch("app.ai.explainer.Phase3Explainer.generate_roadmap", new=AsyncMock(return_value=mock_roadmap)),
        patch.object(orchestrator.link_processor.validator, "validate_many", new=AsyncMock(return_value={
            "https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction": {"status": "ok", "status_code": 200},
            "https://learn.microsoft.com/en-us/azure/security/fundamentals/overview": {"status": "ok", "status_code": 200},
            "https://learn.microsoft.com/en-us/azure/azure-monitor/overview": {"status": "ok", "status_code": 200},
            "https://langchain-ai.github.io/langgraph/": {"status": "ok", "status_code": 200},
        })),
    ):
        payload = await orchestrator.process({"resume": resume, "jd_text": jd})

    assert payload["score_breakdown"]["domain_match"] == 85
    assert "domain_match" in payload["domain_analysis"]
    assert payload["seniority_analysis"]["years_experience"] > 0

    html_out = outlook.generate_professional_html_report(
        candidate_name="Aarav Sharma",
        target_role="Ai Engineer",
        analysis=payload,
        matched_from_sharepoint=True,
        sharepoint_source_file="ai engineer.pdf",
    )

    assert "Domain Match" in html_out
    assert "Domain: Software Eng" not in html_out
    assert "Microsoft Learn: Security Fundamentals Overview" in html_out
    assert "Microsoft Learn: Azure Monitor Overview" in html_out
    assert "Aws Cloud Practitioner Essentials" not in html_out
    assert "domain mismatch" not in html_out.lower()


# ---------------------------------------------------------------------------
# 7. Batch Cloud Coherence (Azure / AWS / GCP), Seniority Rule & Security
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_cloud_isolation_across_ambiguous_sibling_skills():
    retriever = KnowledgeRetriever()
    await retriever.initialize_and_index_catalogs()

    # Case 1: Azure gaps + ambiguous "Modular Provider Integrations" -> ZERO AWS or GCP resources
    azure_results = await retriever.search_for_gaps(
        skills=["Azure Blob Storage", "Modular Provider Integrations", "LangGraph"],
        domain="tech",
        limit=8,
        context_text="Looking for an AI Engineer experienced in Microsoft Azure, Blob Storage, and modular integrations.",
    )
    azure_urls = [str(r.url).lower() for r in azure_results]
    assert not any("skillbuilder.aws" in u or "cloud.google.com" in u for u in azure_urls)
    assert any("learn.microsoft.com/en-us/azure" in u for u in azure_urls)

    # Case 2: AWS JD -> AWS suggestions, ZERO Azure or GCP resources
    aws_results = await retriever.search_for_gaps(
        skills=["Cloud Architecture", "Modular Provider Integrations", "S3"],
        domain="tech",
        limit=6,
        context_text="Hiring AWS Cloud AI Engineer using Amazon Web Services, EC2, and S3.",
    )
    aws_urls = [str(r.url).lower() for r in aws_results]
    assert any("skillbuilder.aws" in u for u in aws_urls)
    assert not any("learn.microsoft.com/en-us/azure" in u or "cloud.google.com" in u for u in aws_urls)

    # Case 3: Google Cloud (GCP) JD -> GCP resources, ZERO AWS or Azure resources
    gcp_results = await retriever.search_for_gaps(
        skills=["Vertex AI", "BigQuery", "Modular Provider Integrations"],
        domain="tech",
        limit=6,
        context_text="Looking for Google Cloud Platform (GCP) Engineer skilled in Vertex AI and BigQuery.",
    )
    gcp_urls = [str(r.url).lower() for r in gcp_results]
    assert any("cloud.google.com" in u for u in gcp_urls)
    assert not any("skillbuilder.aws" in u or "learn.microsoft.com/en-us/azure" in u for u in gcp_urls)


def test_semantic_cache_isolates_cloud_vendor_scopes():
    from app.knowledge.semantic_cache import SemanticVectorCache

    cache = SemanticVectorCache(similarity_threshold=0.90)
    vec = [1.0, 0.0, 0.0]
    aws_dummy = [SimpleNamespace(resource=SimpleNamespace(id="tech-aws"), score=0.9, matched_skills=["cloud"])]
    cache.set("security", vec, aws_dummy, domain="tech", jurisdiction="GLOBAL", vendor_scope="aws")

    assert cache.get(vec, domain="tech", jurisdiction="GLOBAL", vendor_scope="aws") == aws_dummy
    assert cache.get(vec, domain="tech", jurisdiction="GLOBAL", vendor_scope="azure") is None
    assert cache.get(vec, domain="tech", jurisdiction="GLOBAL", vendor_scope="ANY") is None


@pytest.mark.asyncio
async def test_seniority_shortfall_prompt_forbids_aligns_with_and_sas_acronym():
    explainer = Phase3Explainer()
    captured = {}

    async def fake_structured(prompt, output_schema, **kwargs):
        captured["prompt"] = prompt
        return {"executive_summary": "ok", "ats_optimization": {}, "seniority_alignment": {}}

    explainer.client.generate_structured_content = fake_structured
    await explainer.generate_holistic_insights(
        score=51,
        strengths=["Python"],
        gaps=["Azure Blob Storage"],
        years_experience=1.3,
        required_years=3,
        your_level="Entry",
        required_level="Mid",
        seniority_gap=1.7,
        domain_analysis={"resume_domain": "software_engineering", "jd_domain": "data_science", "domain_match": True, "is_compatible_transition": True, "is_mismatch": False},
    )
    assert "SHORTFALL" in captured["prompt"]
    assert "Do NOT write that candidate experience 'aligns with' or 'meets'" in captured["prompt"]

    svc = OutlookService()
    assert svc._derive_readable_link_title("https://learn.microsoft.com/en-us/azure/storage/blobs/sas-service-create") == "Microsoft Learn: SAS Service Create"
    assert svc._derive_readable_link_title("https://reference.langchain.com/python/agents") == "LangChain Docs: Agents"
    assert svc._derive_readable_link_title("https://docs.langchain.com/oss/python/langchain/overview") == "LangChain Docs: LangChain Overview"
    assert svc._derive_readable_link_title("https://learn.microsoft.com/en-us/search/?terms=Chatgpt+quickstart") == "Microsoft Learn: ChatGPT Quickstart"

    long_rag_pill = svc._derive_readable_link_title(
        "https://learn.microsoft.com/en-us/search/?terms=Implement+Retrieval-Augmented+Generation+Using+Azure+OpenAI"
    )
    assert "Retrieval-Augmented" in long_rag_pill
    assert len(long_rag_pill) <= 56
    assert long_rag_pill.endswith("...")
    assert not long_rag_pill.endswith("Op...")


def test_security_ssrf_and_admin_key_enforcement():
    from fastapi import HTTPException
    from app.utils.security import validate_public_http_url, require_admin_access
    import asyncio

    for blocked in (
        "http://127.0.0.1:8000/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost/admin",
        "file:///etc/passwd",
        "http://10.0.0.5/internal",
    ):
        with pytest.raises(ValueError):
            validate_public_http_url(blocked)

    with patch("app.utils.security.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
        assert validate_public_http_url("https://example.com/careers/ai-engineer") == "https://example.com/careers/ai-engineer"

    with patch.object(settings, "admin_api_key", "super-secret-admin-key"), patch.object(settings, "debug", False):
        asyncio.run(require_admin_access(x_admin_key="super-secret-admin-key"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_admin_access(x_admin_key="wrong-key"))
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc_missing:
            asyncio.run(require_admin_access(x_admin_key=None))
        assert exc_missing.value.status_code == 403


@pytest.mark.asyncio
async def test_sharepoint_rejects_oversized_jd_file():
    from app.services.sharepoint_service import SharePointService

    sp = SharePointService(site_url="https://contoso.sharepoint.com/sites/HR", folder_path="JDs")
    mock_graph = AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {
        "value": [{"id": "huge-1", "name": "huge_jd.pdf", "size": 50 * 1024 * 1024}]
    }))
    with (
        patch.object(sp, "is_configured", return_value=True),
        patch.object(sp, "resolve_site_and_drive", AsyncMock(return_value=("s1", "d1"))),
        patch.object(sp, "_get_auth_headers", AsyncMock(return_value={"Authorization": "Bearer tok"})),
        patch("app.services.sharepoint_service.outlook_service._graph_request", mock_graph),
    ):
        jds = await sp.fetch_active_job_descriptions(force_refresh=True)
    assert jds == []
    assert mock_graph.await_count == 1  # Never downloaded the 50MB payload


