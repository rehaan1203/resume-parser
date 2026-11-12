"""
Unit and Integration Tests for Microsoft SharePoint Job Description Service.

Verifies SharePoint URL parsing, site resolution, in-memory JD streaming (DOCX, PDF, TXT),
smart role routing, open-application best-fit selection, and Outlook integration.
"""

import asyncio
import io
import sys
from unittest.mock import AsyncMock, MagicMock, patch

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import docx
import pytest
from PyPDF2 import PdfWriter

from app.services.sharepoint_service import SharePointService
from app.services.outlook_service import OutlookService


@pytest.fixture
def mock_sharepoint_service():
    """Create a SharePointService instance with test configurations."""
    return SharePointService(
        site_url="https://sstlab.sharepoint.com/sites/HR",
        folder_path="Shared Documents/JobDescriptions",
        cache_ttl_seconds=300,
    )


@pytest.fixture
def sample_docx_jd_bytes():
    """Generate in-memory synthetic DOCX bytes containing a Job Description."""
    doc = docx.Document()
    doc.add_heading("Senior Python Backend Engineer", 0)
    doc.add_paragraph("About the Role: We are seeking a Senior Python Engineer to lead backend microservices architecture.")
    doc.add_paragraph("Key Responsibilities: Design and maintain REST APIs using FastAPI, PostgreSQL, Redis, and Docker.")
    doc.add_paragraph("Requirements: 5+ years with Python, asynchronous programming, Kubernetes, CI/CD, and distributed caching.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_pdf_jd_bytes():
    """Generate in-memory synthetic PDF bytes containing a Cloud Security Job Description."""
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_sharepoint_service_configuration(mock_sharepoint_service):
    """Verify configuration status checks."""
    with patch("app.services.sharepoint_service.outlook_service.is_configured", return_value=True):
        assert mock_sharepoint_service.is_configured() is True

    unconfigured = SharePointService(site_url="", folder_path="")
    assert unconfigured.is_configured() is False


def test_site_url_parsing(mock_sharepoint_service):
    """Verify URL extraction into hostname and server-relative path."""
    host, path = mock_sharepoint_service._parse_site_url()
    assert host == "sstlab.sharepoint.com"
    assert path == "sites/HR"

    root_svc = SharePointService(site_url="https://sstlab.sharepoint.com", folder_path="JDs")
    r_host, r_path = root_svc._parse_site_url()
    assert r_host == "sstlab.sharepoint.com"
    assert r_path == ""


def test_in_memory_docx_jd_extraction(mock_sharepoint_service, sample_docx_jd_bytes):
    """Verify in-memory extraction of DOCX text without disk storage."""
    text = mock_sharepoint_service._extract_jd_text_in_memory(sample_docx_jd_bytes, "docx", "Python_JD.docx")
    assert "Senior Python Backend Engineer" in text
    assert "FastAPI, PostgreSQL, Redis" in text
    assert len(text) > 80


def test_in_memory_pdf_jd_extraction_mocked(mock_sharepoint_service):
    """Verify PDF extraction handling in memory."""
    synthetic_text = "Cloud Security Engineer\nRequired: AWS IAM, Sentinel, Kubernetes security, and Terraform."
    with patch("pdfplumber.open") as mock_plumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = synthetic_text
        mock_pdf.pages = [mock_page]
        mock_plumber.return_value.__enter__.return_value = mock_pdf

        text = mock_sharepoint_service._extract_jd_text_in_memory(b"%PDF dummy", "pdf", "Security_JD.pdf")
        assert "Cloud Security Engineer" in text
        assert "Sentinel, Kubernetes" in text


def test_clean_job_title(mock_sharepoint_service):
    """Verify job title normalization from filename."""
    assert mock_sharepoint_service._clean_job_title("Senior_Python_Backend_Developer_JD.docx", "") == "Senior Python Backend Developer"
    assert mock_sharepoint_service._clean_job_title("Cloud-Security-Engineer-final-v2.pdf", "") == "Cloud Security Engineer"
    assert mock_sharepoint_service._clean_job_title("Corporate_Legal_Counsel.docx", "") == "Corporate Legal Counsel"


@pytest.mark.asyncio
async def test_role_specified_matching(mock_sharepoint_service):
    """Verify candidate specifying a role matches the corresponding SharePoint JD."""
    mock_jds = [
        {
            "id": "jd-1",
            "title": "Senior Python Backend Engineer",
            "filename": "Senior_Python_Engineer.docx",
            "text": "FastAPI, PostgreSQL, Redis, Python backend systems.",
        },
        {
            "id": "jd-2",
            "title": "Cloud Security Specialist",
            "filename": "Cloud_Security.pdf",
            "text": "AWS IAM, Azure Sentinel, SIEM, SOC compliance.",
        },
    ]

    with patch.object(mock_sharepoint_service, "fetch_active_job_descriptions", AsyncMock(return_value=mock_jds)):
        result = await mock_sharepoint_service.find_best_matching_jd(
            candidate_resume_text="Experienced developer with Python and web frameworks.",
            preferred_role="Application for Senior Python Developer",
        )

        assert result["found"] is True
        assert result["job_title"] == "Senior Python Backend Engineer"
        assert result["source_file"] == "Senior_Python_Engineer.docx"
        assert result["selection_mode"] == "role_specified"


@pytest.mark.asyncio
async def test_open_application_best_fit_routing(mock_sharepoint_service):
    """Verify general application with no role specified routes to the highest-scoring SharePoint opening."""
    mock_jds = [
        {
            "id": "jd-1",
            "title": "Senior Python Backend Engineer",
            "filename": "Python_Engineer.docx",
            "text": "Requires Python, Django, FastAPI, Docker, Microservices, and SQL databases.",
        },
        {
            "id": "jd-2",
            "title": "Corporate Compliance Legal Counsel",
            "filename": "Legal_Counsel.docx",
            "text": "Requires Law degree, Contract drafting, DPDP Act, and corporate governance.",
        },
    ]

    cloud_resume = (
        "Jane Doe - Software Engineer. 5 years building scalable web services in Python, "
        "FastAPI, Docker, Microservices, and PostgreSQL database queries."
    )

    with patch.object(mock_sharepoint_service, "fetch_active_job_descriptions", AsyncMock(return_value=mock_jds)):
        # Candidate did NOT specify any role
        result = await mock_sharepoint_service.find_best_matching_jd(
            candidate_resume_text=cloud_resume,
            preferred_role=None,
        )

        assert result["found"] is True
        # Should automatically select Python Backend Engineer over Legal Counsel
        assert result["job_title"] == "Senior Python Backend Engineer"
        assert result["selection_mode"] == "best_fit_routed"
        assert result["match_confidence"] > 0.0


@pytest.mark.asyncio
async def test_sharepoint_outlook_integration_end_to_end(sample_docx_jd_bytes):
    """Verify that OutlookService seamlessly evaluates candidate against active SharePoint JD."""
    outlook_svc = OutlookService(
        tenant_id="t1",
        client_id="c1",
        client_secret="s1",
        mailbox_email="a.rehaan@sstlab.in",
    )

    mock_sp_match = {
        "found": True,
        "job_title": "Senior Python Backend Engineer",
        "jd_text": "Requires FastAPI, PostgreSQL, Redis, Python architecture.",
        "source_file": "Senior_Python_Backend.docx",
        "selection_mode": "best_fit_routed",
    }

    mock_analysis_result = {
        "overall_score": 86,
        "executive_summary": "High alignment for Senior Python role from SharePoint library.",
        "strengths": ["FastAPI", "Python"],
        "skill_gaps": ["Redis"],
        "score_breakdown": {"skills_match": 88, "seniority_match": 84, "domain_match": 86},
        "resume_domain": "Tech",
        "roadmap": {},
    }

    mock_orchestrator = MagicMock()
    mock_orchestrator.process = AsyncMock(return_value=mock_analysis_result)

    mock_message = {
        "id": "msg-sp-1",
        "subject": "My Resume for Open Opportunities",
        "from": {"emailAddress": {"name": "Alex Taylor", "address": "alex@example.com"}},
        "hasAttachments": True,
    }

    mock_attachment = [
        {
            "name": "Alex_Resume.txt",
            "contentType": "text/plain",
            "contentBytes": "QWxleCBUYXlsb3IgLSBQeXRob24gRGV2ZWxvcGVyIHdpdGggNCB5ZWFycyBGYXN0QVBJIGFuZCBQb3N0Z3JlU1FM",  # Base64 for resume text
        }
    ]

    with patch("app.services.sharepoint_service.sharepoint_service.is_configured", return_value=True), \
         patch("app.services.sharepoint_service.sharepoint_service.find_best_matching_jd", AsyncMock(return_value=mock_sp_match)), \
         patch.object(outlook_svc, "fetch_attachments", AsyncMock(return_value=mock_attachment)), \
         patch.object(outlook_svc, "send_reply_email", AsyncMock(return_value=True)) as mock_send, \
         patch.object(outlook_svc, "mark_message_as_read", AsyncMock(return_value=True)):

        result = await outlook_svc.process_candidate_message(mock_message, mock_orchestrator)

        assert result["status"] == "processed"
        assert result["matchedFromSharePoint"] is True
        assert result["sharepointFile"] == "Senior_Python_Backend.docx"
        assert result["emailSent"] is True

        # Verify email reply references the SharePoint opening
        mock_send.assert_awaited_once()
        _, kwargs = mock_send.call_args
        assert "Senior Python Backend Engineer" in kwargs["subject"]
        assert "Senior_Python_Backend.docx" in kwargs["html_body"]


def test_docx_table_jd_extraction_and_stopword_hygiene(mock_sharepoint_service):
    """Verify DOCX JDs stored inside Word tables are extracted cleanly and stopwords are excluded."""
    doc = docx.Document()
    doc.add_paragraph("Job Overview: Staff Platform Engineer")
    tbl = doc.add_table(rows=2, cols=2)
    tbl.cell(0, 0).text = "Core Stack"
    tbl.cell(0, 1).text = "Kubernetes, Terraform, Go, Kafka"
    tbl.cell(1, 0).text = "Experience"
    tbl.cell(1, 1).text = "6+ years distributed systems"
    buf = io.BytesIO()
    doc.save(buf)

    text = mock_sharepoint_service._extract_jd_text_in_memory(buf.getvalue(), "docx", "Platform_JD.docx")
    assert "Staff Platform Engineer" in text
    assert "Kubernetes, Terraform, Go, Kafka" in text
    assert "6+ years distributed systems" in text
    assert "the" in mock_sharepoint_service._COMMON_STOPWORDS


@pytest.mark.asyncio
async def test_case_insensitive_subject_prefix_matching(mock_sharepoint_service):
    """Verify FW:/RE:/Resume-noise email subjects cleanly match the right SharePoint JD."""
    mock_jds = [
        {"id": "jd-1", "title": "Ai Engineer", "filename": "ai_engineer.pdf", "text": "PyTorch, LLMs, Python"},
        {"id": "jd-2", "title": "Accountant", "filename": "accountant.docx", "text": "GAAP, Audit, Tax"},
    ]
    with patch.object(mock_sharepoint_service, "fetch_active_job_descriptions", AsyncMock(return_value=mock_jds)):
        res = await mock_sharepoint_service.find_best_matching_jd(
            candidate_resume_text="Python FastAPI PyTorch",
            preferred_role="FW: RE: Resume attached for AI Engineer role",
        )
        assert res["found"] is True
        assert res["job_title"] == "Ai Engineer"
        assert res["selection_mode"] == "role_specified"


@pytest.mark.asyncio
async def test_open_application_minimum_confidence_threshold(mock_sharepoint_service):
    """Verify Case 2 rejects completely unrelated candidates rather than force-matching an incompatible JD."""
    mock_jds = [
        {
            "id": "jd-ai",
            "title": "Ai Engineer",
            "filename": "ai_engineer.pdf",
            "text": "PyTorch Transformers CUDA Deep Learning Fine-Tuning VectorDB LangChain",
        }
    ]
    unrelated_resume = "Licensed Commercial HVAC Technician skilled in EPA 608 refrigeration brazing and boilers."
    with patch.object(mock_sharepoint_service, "fetch_active_job_descriptions", AsyncMock(return_value=mock_jds)):
        res = await mock_sharepoint_service.find_best_matching_jd(
            candidate_resume_text=unrelated_resume,
            preferred_role=None,
        )
        assert res["found"] is False

