"""
Unit and Integration Tests for Microsoft Outlook HR Agent Service.

Verifies in-memory resume streaming (PDF, DOCX, email body), role inference,
professional HTML report generation, and automated MS Graph email reply workflow.
"""

import asyncio
import base64
import io
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import docx
import pytest
from PyPDF2 import PdfWriter

from app.services.outlook_service import OutlookService
from app.services.sharepoint_service import SharePointService


@pytest.fixture
def mock_outlook_service():
    """Create an OutlookService instance with test credentials."""
    return OutlookService(
        tenant_id="test-tenant-id-1234",
        client_id="test-client-id-5678",
        client_secret="test-client-secret-9999",
        mailbox_email="friction.agent@example.com",
    )


@pytest.fixture
def sample_pdf_bytes():
    """Generate in-memory synthetic PDF bytes containing resume text."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def sample_docx_bytes():
    """Generate in-memory synthetic DOCX bytes containing resume text."""
    doc = docx.Document()
    doc.add_heading("Jane Doe - Senior Python Developer", 0)
    doc.add_paragraph("Summary: Experienced backend engineer specializing in FastAPI, PostgreSQL, Docker, and Microservices.")
    doc.add_paragraph("Skills: Python, FastAPI, Docker, Kubernetes, AWS, PostgreSQL, Redis, CI/CD.")
    doc.add_paragraph("Experience: 5 years building high-throughput distributed systems.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_outlook_service_configuration(mock_outlook_service):
    """Verify that credentials check behaves correctly."""
    assert mock_outlook_service.is_configured() is True
    assert mock_outlook_service.mailbox_email == "friction.agent@example.com"

    unconfigured = OutlookService(tenant_id="", client_id="", client_secret="", mailbox_email="")
    assert unconfigured.is_configured() is False


def test_in_memory_docx_extraction(mock_outlook_service, sample_docx_bytes):
    """Verify extraction of resume text directly from in-memory DOCX bytes (zero disk I/O)."""
    b64_content = base64.b64encode(sample_docx_bytes).decode("utf-8")
    attachments = [
        {
            "name": "Jane_Doe_Resume.docx",
            "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "contentBytes": b64_content,
        }
    ]
    message = {"id": "msg-1", "body": {"content": "Please find attached my resume."}}

    text, source = mock_outlook_service.extract_resume_text_in_memory(message, attachments)

    assert source == "Jane_Doe_Resume.docx"
    assert "Jane Doe - Senior Python Developer" in text
    assert "FastAPI, PostgreSQL, Docker" in text
    assert len(text) > 100


def test_in_memory_pdf_extraction_mocked(mock_outlook_service):
    """Verify PDF extraction falls back cleanly and extracts text in memory."""
    synthetic_pdf_text = "Alex Mercer - Senior Cloud Architect\n10+ years experience in AWS, Kubernetes, Terraform, Python."

    with patch.object(mock_outlook_service, "_extract_pdf_in_memory", return_value=synthetic_pdf_text):
        dummy_b64 = base64.b64encode(b"%PDF-1.4 dummy").decode("utf-8")
        attachments = [
            {
                "name": "Alex_Mercer_CV.pdf",
                "contentType": "application/pdf",
                "contentBytes": dummy_b64,
            }
        ]
        message = {"id": "msg-2", "body": {"content": "Attached resume"}}

        text, source = mock_outlook_service.extract_resume_text_in_memory(message, attachments)
        assert source == "Alex_Mercer_CV.pdf"
        assert "Alex Mercer" in text
        assert "Kubernetes, Terraform" in text


def test_email_body_resume_fallback(mock_outlook_service):
    """Verify that when no attachment is provided, resume text in email body is extracted."""
    body_text = (
        "Hello Hiring Team,\n\n"
        "Here is my resume:\n"
        "Name: Jordan Smith\n"
        "Role: Full Stack React & Node Developer\n"
        "Experience: 4 years building scalable web applications with React, Next.js, and Express.\n"
        "Skills: TypeScript, JavaScript, React, TailwindCSS, PostgreSQL."
    )
    message = {
        "id": "msg-3",
        "body": {
            "contentType": "Text",
            "content": body_text,
        },
    }

    text, source = mock_outlook_service.extract_resume_text_in_memory(message, attachments=[])
    assert source == "email_body"
    assert "Jordan Smith" in text
    assert "Full Stack React & Node Developer" in text


def test_target_role_inference(mock_outlook_service):
    """Verify regex-based role extraction from subject lines."""
    # Pattern: Application for X
    jd1 = mock_outlook_service.infer_target_role_and_jd("Application for Senior Python Backend Engineer", "")
    assert "Senior Python Backend Engineer" in jd1

    # Pattern: Applying for X
    jd2 = mock_outlook_service.infer_target_role_and_jd("Applying for Corporate Legal Counsel - Jane Doe", "")
    assert "Corporate Legal Counsel" in jd2

    # Pattern: X - Resume
    jd3 = mock_outlook_service.infer_target_role_and_jd("DevOps Cloud Specialist - Resume", "")
    assert "DevOps Cloud Specialist" in jd3

    # Fallback when generic subject
    jd4 = mock_outlook_service.infer_target_role_and_jd("My Resume", "")
    assert "Job Title: Domain Professional / Specialist." in jd4


def test_professional_html_report_rendering(mock_outlook_service):
    """Verify that generated HTML report contains professional scorecard, verdict, links, and roadmap."""
    mock_analysis = {
        "overall_score": 84,
        "executive_summary": "Strong candidate with comprehensive background in distributed systems and backend design.",
        "strengths": [
            "Extensive experience in FastAPI and asynchronous Python architectures.",
            "Demonstrated database design with PostgreSQL and Redis caching.",
        ],
        "skill_gaps": [
            "Kubernetes orchestration and production cluster monitoring.",
        ],
        "score_breakdown": {
            "skills_match": 88,
            "seniority_match": 82,
            "domain_match": 85,
        },
        "resume_domain": "Tech",
        "roadmap": {
            "resources": [
                {
                    "title": "FastAPI Production Best Practices",
                    "url": "https://fastapi.tiangolo.com/tutorial/",
                    "platform": "Official Documentation",
                },
                {
                    "title": "AWS Certified Solutions Architect",
                    "url": "https://aws.amazon.com/certification/",
                    "platform": "AWS Skill Builder",
                },
            ]
        },
    }

    html = mock_outlook_service.generate_professional_html_report(
        candidate_name="Jane Doe",
        target_role="Senior Python Backend Engineer",
        analysis=mock_analysis,
    )

    # Assert essential structural elements
    assert "Jane Doe" in html
    assert "Senior Python Backend Engineer" in html
    assert "84%" in html
    assert "Strong Fit" in html
    assert "Strong candidate with comprehensive background" in html
    assert "FastAPI and asynchronous Python architectures" in html
    assert "Kubernetes orchestration" in html
    assert "https://fastapi.tiangolo.com/tutorial/" in html
    assert "AWS Certified Solutions Architect" in html
    assert "Days 1 - 30: Foundational Mastery" in html
    assert "Days 31 - 60: Applied Projects" in html
    assert "Friction Matcher AI Talent Suite" in html
    assert "In adherence to strict privacy standards" in html


@pytest.mark.asyncio
async def test_end_to_end_process_candidate_message_mocked(mock_outlook_service, sample_docx_bytes):
    """Verify complete lifecycle of an incoming email: parse in-memory, analyze, send email reply, and mark read."""
    b64_docx = base64.b64encode(sample_docx_bytes).decode("utf-8")
    mock_message = {
        "id": "msg-101",
        "subject": "Application for Senior Python Backend Engineer",
        "from": {
            "emailAddress": {
                "name": "Jane Doe",
                "address": "janedoe@example.com",
            }
        },
        "hasAttachments": True,
    }

    mock_attachments = [
        {
            "name": "Jane_Doe_Resume.docx",
            "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "contentBytes": b64_docx,
        }
    ]

    mock_analysis_result = {
        "overall_score": 88,
        "executive_summary": "Excellent alignment for backend engineering role.",
        "strengths": ["Python", "FastAPI"],
        "skill_gaps": ["Kubernetes"],
        "score_breakdown": {"skills_match": 90, "seniority_match": 85, "domain_match": 88},
        "resume_domain": "Tech",
        "roadmap": {},
    }

    mock_orchestrator = MagicMock()
    mock_orchestrator.process = AsyncMock(return_value=mock_analysis_result)

    with patch.object(mock_outlook_service, "fetch_attachments", AsyncMock(return_value=mock_attachments)), \
         patch.object(SharePointService, "is_configured", return_value=False), \
         patch.object(mock_outlook_service, "send_reply_email", AsyncMock(return_value=True)) as mock_send, \
         patch.object(mock_outlook_service, "mark_message_as_read", AsyncMock(return_value=True)) as mock_read:

        result = await mock_outlook_service.process_candidate_message(mock_message, mock_orchestrator)

        assert result["status"] == "processed"
        assert result["sender"] == "janedoe@example.com"
        assert result["candidateName"] == "Jane Doe"
        assert result["overallScore"] == 88
        assert result["emailSent"] is True

        # Verify that an email was sent to the candidate
        mock_send.assert_awaited_once()
        args, kwargs = mock_send.call_args
        assert kwargs["to_address"] == "janedoe@example.com"
        assert "Senior Python Backend Engineer" in kwargs["subject"]
        assert "Jane Doe" in kwargs["html_body"]

        # Verify message was marked as read (idempotency)
        mock_read.assert_awaited_once_with("msg-101")


@pytest.mark.asyncio
async def test_missing_attachment_handling(mock_outlook_service):
    """Verify graceful handling when candidate sends an email with no resume attached."""
    mock_message = {
        "id": "msg-102",
        "subject": "Inquiry about job openings",
        "from": {
            "emailAddress": {
                "name": "Bob Smith",
                "address": "bob@example.com",
            }
        },
        "hasAttachments": False,
        "body": {
            "content": "Hi, are you hiring?",
        },
    }

    mock_orchestrator = MagicMock()

    with patch.object(mock_outlook_service, "send_reply_email", AsyncMock(return_value=True)) as mock_send, \
         patch.object(mock_outlook_service, "mark_message_as_read", AsyncMock(return_value=True)) as mock_read:

        result = await mock_outlook_service.process_candidate_message(mock_message, mock_orchestrator)

        assert result["status"] == "missing_resume"
        assert result["sender"] == "bob@example.com"

        # Verify clarification email sent requesting attachment
        mock_send.assert_awaited_once()
        _, kwargs = mock_send.call_args
        assert "Resume Attachment Required" in kwargs["subject"]
        assert "PDF" in kwargs["html_body"]
        assert "Word (.docx)" in kwargs["html_body"]

        # Verify marked as read
        mock_read.assert_awaited_once_with("msg-102")


@pytest.mark.asyncio
async def test_poll_and_process_inbox_mocked(mock_outlook_service):
    """Verify batch polling returns execution telemetry across multiple candidate messages."""
    unread_emails = [
        {"id": "msg-1", "subject": "App 1", "from": {"emailAddress": {"address": "c1@test.com"}}},
        {"id": "msg-2", "subject": "App 2", "from": {"emailAddress": {"address": "c2@test.com"}}},
    ]

    mock_process_res = {
        "messageId": "msg-1",
        "status": "processed",
        "overallScore": 85,
        "emailSent": True,
    }

    with patch.object(mock_outlook_service, "fetch_unread_candidate_emails", AsyncMock(return_value=unread_emails)), \
         patch.object(mock_outlook_service, "process_candidate_message", AsyncMock(return_value=mock_process_res)):

        summary = await mock_outlook_service.poll_and_process_inbox(limit=10)

        assert summary["success"] is True
        assert summary["processedCount"] == 2
        assert len(summary["results"]) == 2


@pytest.mark.asyncio
async def test_start_background_listener_lifecycle(mock_outlook_service):
    """Verify background listener starts, polls, and cancels cleanly on stop_event."""
    stop_event = asyncio.Event()

    async def trigger_stop(*args, **kwargs):
        stop_event.set()
        return {"success": True, "processedCount": 1}

    with patch.object(mock_outlook_service, "poll_and_process_inbox", side_effect=trigger_stop) as mock_poll:
        await mock_outlook_service.start_background_listener(stop_event)
        mock_poll.assert_awaited_once()
        assert stop_event.is_set() is True


def test_extract_candidate_name_variations(mock_outlook_service):
    """Verify high-accuracy candidate name extraction across text, filename, and fallback."""
    # 1. From resume text header
    resume_with_name = (
        "Aarav Sharma\n"
        "Bangalore, India | aarav.sharma@example.com | +91 9876543210\n"
        "SUMMARY\n"
        "Full stack software engineer with 4 years experience in Python, FastAPI, React."
    )
    name = mock_outlook_service.extract_candidate_name(
        resume_text=resume_with_name,
        attachment_name="document.pdf",
        fallback_sender="Ahmed Rehaan",
    )
    assert name == "Aarav Sharma"

    # 2. From filename when text lacks a clean name
    name_from_fn = mock_outlook_service.extract_candidate_name(
        resume_text="Senior Developer Resume\nTechnical competencies: Python, Docker",
        attachment_name="aarav-sharma-resume.pdf",
        fallback_sender="Ahmed Rehaan",
    )
    assert name_from_fn == "Aarav Sharma"

    # 3. Fallback to sender display name
    name_fallback = mock_outlook_service.extract_candidate_name(
        resume_text="",
        attachment_name="resume.pdf",
        fallback_sender="Jane Recruiter",
    )
    assert name_fallback == "Jane Recruiter"


@pytest.mark.asyncio
async def test_system_email_and_bounce_back_ignored(mock_outlook_service):
    """Verify that automated system notifications and bounce-backs are ignored without calling orchestrator."""
    system_message = {
        "id": "msg-bounce-1",
        "subject": "Undeliverable: Application confirmation",
        "from": {
            "emailAddress": {
                "address": "MSSecurity-noreply@microsoft.com",
                "name": "Microsoft Security",
            }
        },
        "hasAttachments": False,
        "body": {"content": "Delivery has failed to these recipients"},
    }

    mock_orchestrator = MagicMock()

    with patch.object(mock_outlook_service, "mark_message_as_read", AsyncMock(return_value=True)) as mock_read:
        result = await mock_outlook_service.process_candidate_message(system_message, mock_orchestrator)

        assert result["status"] == "ignored_system_email"
        mock_read.assert_awaited_once_with("msg-bounce-1")
        mock_orchestrator.process.assert_not_called()


def test_tech_domain_compatibility():
    """Verify software engineering and data science are recognized as compatible career transitions."""
    from app.utils.domain_detector import analyze_domain

    se_resume = "Software Engineer with 4 years experience building backend APIs with Python, FastAPI, Docker, PostgreSQL."
    ai_jd = "AI Engineer position requiring Machine Learning, Python, PyTorch, LLMs, Deep Learning, and data modeling."

    analysis = analyze_domain(se_resume, ai_jd)
    assert analysis["domain_match"] is True
    assert analysis["is_compatible_transition"] is True
    assert analysis["resume_domain"] == "software_engineering"
    assert analysis["jd_domain"] == "data_science"


def test_rich_frontend_parity_email_report_rendering(mock_outlook_service):
    """Verify full frontend-parity HTML rendering: verified_resources, weekly roadmap links, ATS, seniority, friction, and domain transition."""
    rich_analysis = {
        "overall_score": 51,
        "executive_summary": "Strong Python & Docker skills with 2-year seniority gap.",
        "score_breakdown": {"skills_match": 50, "seniority_match": 60, "domain_match": 85},
        "domain_analysis": {"resume_domain": "software_engineering", "jd_domain": "data_science", "domain_match": True},
        "strengths": ["Docker", "Python"],
        "skill_gaps": ["Azure", "Kubernetes", "Machine Learning"],
        "seniority_analysis": {
            "your_level": "Mid",
            "required_level": "Senior",
            "years_experience": 3,
            "required_years": 5,
            "alignment_badge": "MINOR GAP",
            "summary": "Candidate has 3 years vs 5 required years.",
            "recommendation": "Highlight architectural ownership.",
        },
        "friction_points": [
            {
                "category": "experience",
                "severity": "medium",
                "description": "2-year gap in senior leadership.",
                "suggestion": "Showcase production ownership on ML pipelines.",
            }
        ],
        "ats_optimization": {
            "keywords": ["PyTorch", "Kubernetes", "Azure ML"],
            "phrasing": [{"original": "Built backend services", "suggested": "Architected scalable AI microservices"}],
            "formatting_tips": ["Move Cloud & ML skills near top"],
        },
        "roadmap": {
            "title": "Short Upskill Roadmap (4 Weeks)",
            "verified_resources": [
                {
                    "title": "Microsoft Azure Cloud Services",
                    "url": "https://www.coursera.org/learn/microsoft-azure-cloud-services",
                    "platform": "Coursera",
                    "skill": "Azure",
                }
            ],
            "weeks": [
                {
                    "week": 1,
                    "focus": "Azure & Cloud Infrastructure",
                    "days": [
                        {
                            "day": 1,
                            "action": "Complete Azure Fundamentals intro",
                            "estimated_time": "2 hours",
                            "resources": ["[Azure Fundamentals](https://learn.microsoft.com/en-us/training/modules/intro-to-azure-fundamentals/)"],
                        }
                    ],
                }
            ],
        },
    }

    html_out = mock_outlook_service.generate_professional_html_report(
        candidate_name="Aarav Sharma",
        target_role="Ai Engineer",
        analysis=rich_analysis,
        matched_from_sharepoint=True,
        sharepoint_source_file="ai engineer.pdf",
    )

    assert "Aarav Sharma" in html_out
    assert "Domain Match" in html_out
    assert "Domain: Software Eng" not in html_out
    assert "Microsoft Azure Cloud Services" in html_out
    assert "https://www.coursera.org/learn/microsoft-azure-cloud-services" in html_out
    assert "Short Upskill Roadmap (4 Weeks)" in html_out
    assert "Week 1: Azure &amp; Cloud Infrastructure" in html_out
    assert "Complete Azure Fundamentals intro" in html_out
    assert "https://learn.microsoft.com/en-us/training/modules/intro-to-azure-fundamentals/" in html_out
    assert "ATS Resume Optimization Playbook" in html_out
    assert "Architected scalable AI microservices" in html_out
    assert "Experience &amp; Seniority Calibration" in html_out
    assert "Key Friction Points &amp; Risk Mitigation" in html_out


def test_poller_pause_resume_state(mock_outlook_service):
    """Verify runtime pause and resume toggles background poller state cleanly."""
    assert mock_outlook_service.is_poller_paused() is False
    mock_outlook_service.pause_poller()
    assert mock_outlook_service.is_poller_paused() is True
    mock_outlook_service.resume_poller()
    assert mock_outlook_service.is_poller_paused() is False


def test_readable_link_titles_and_frontend_zinc_layout(mock_outlook_service):
    """Verify raw URLs become crisp human titles and Frontend-parity Neutral Zinc Light/Dark + CID icon layout."""
    ms_title = mock_outlook_service._derive_readable_link_title(
        "https://learn.microsoft.com/en-us/training/modules/intro-to-azure-fundamentals/"
    )
    k8s_title = mock_outlook_service._derive_readable_link_title(
        "https://kubernetes.io/docs/concepts/workloads/pods/"
    )
    coursera_title = mock_outlook_service._derive_readable_link_title(
        "https://www.coursera.org/courses?query=microsoft+azure"
    )
    yt_title = mock_outlook_service._derive_readable_link_title(
        "https://www.youtube.com/watch?v=Jfvg3csBUy4", fallback_context="Docker Networking"
    )

    assert "Microsoft Learn:" in ms_title and "Azure Fundamentals" in ms_title
    assert k8s_title == "Kubernetes Docs: Pods"
    assert coursera_title == "Coursera: Microsoft Azure"
    assert yt_title == "YouTube Video: Docker Networking"

    raw_url_analysis = {
        "overall_score": 68,
        "executive_summary": "Solid software base transitioning to AI.",
        "score_breakdown": {"skills_match": 65, "seniority_match": 70, "domain_match": 85},
        "domain_analysis": {"resume_domain": "software_engineering", "jd_domain": "data_science"},
        "strengths": ["Python"],
        "skill_gaps": ["Kubernetes"],
        "seniority_analysis": {
            "your_level": "Entry",
            "required_level": "Mid",
            "years_experience": 1,
            "required_years": 3,
            "alignment_status": "minor_gap",
            "alignment_badge": "🟡 MINOR GAP",
        },
        "roadmap": {
            "title": "Upskill Roadmap",
            "weeks": [
                {
                    "week": 1,
                    "focus": "Containers & Orchestration",
                    "days": [
                        {
                            "day": 1,
                            "action": "Learn about Pods",
                            "estimated_time": "1 hour",
                            "resources": ["https://kubernetes.io/docs/concepts/workloads/pods/"],
                        }
                    ],
                }
            ],
        },
    }

    html_out = mock_outlook_service.generate_professional_html_report(
        candidate_name="Aarav Sharma",
        target_role="Ai Engineer",
        analysis=raw_url_analysis,
        matched_from_sharepoint=True,
        sharepoint_source_file="ai engineer.pdf",
    )

    # Neutral Zinc Light-First palette + Inter typography + Outlook Dark Mode safeguards (zero linear-gradient gray shifting)
    assert "#FFFFFF" in html_out
    assert "#FAFAFA" in html_out
    assert "#E4E4E7" in html_out
    assert "#09090B" in html_out
    assert "'Inter'" in html_out
    assert "linear-gradient" not in html_out
    assert 'name="color-scheme" content="light dark"' in html_out
    assert "[data-ogsb] .fm-card" in html_out
    # Crisp CID vector icons replace all raw emojis
    assert 'src="cid:icon-check"' in html_out
    assert 'src="cid:icon-alert-triangle"' in html_out
    assert 'src="cid:icon-file"' in html_out
    assert 'src="cid:icon-user-check"' in html_out
    assert "&#128196;" not in html_out
    assert "&#10003;" not in html_out
    assert "&#9888;" not in html_out
    assert "🟡" not in html_out
    assert "MINOR GAP" in html_out
    # Human-readable title displayed instead of bare URL as link label
    assert ">Kubernetes Docs: Pods" in html_out
    # Action button must not wrap vertically & must use Outlook-safe arrows (&rarr;, never &nearr;)
    assert "table-layout: fixed;" in html_out
    assert "white-space: nowrap;" in html_out
    assert "&nearr;" not in html_out
    assert "&rarr;" in html_out


def test_scoped_tls_email_icons_and_attachment_fallbacks(mock_outlook_service):
    """Verify global httpx.AsyncClient TLS stays strict, CID PNGs load, PII logs mask emails, and _raw_bytes / .doc work."""
    import httpx
    from app.services.outlook_service import _load_email_icon_b64, _mask_email
    from app.ai.client import GenAIClient

    # 1. Global httpx.AsyncClient must NOT be monkeypatched with UnverifiedAsyncClient
    assert httpx.AsyncClient.__name__ == "AsyncClient"
    assert hasattr(GenAIClient, "_interactive_waiters")

    # 2. All CID vector icons load cleanly
    for icon_id in [
        "icon-file", "icon-check", "icon-alert-triangle", "icon-alert-circle",
        "icon-info", "icon-user-check", "icon-trending", "icon-target",
        "icon-book", "icon-calendar",
    ]:
        assert _load_email_icon_b64(icon_id)

    # 3. Email masking redacts PII
    assert _mask_email("aarav.sharma@example.com") == "aa***@example.com"

    # 4. In-memory _raw_bytes (>3MB /$value stream) & legacy .doc fallback work
    raw_doc = b"\x00\x00Aarav Sharma Senior Python Engineer with 5 years experience in FastAPI Docker Kubernetes\x00\x00"
    text, src = mock_outlook_service.extract_resume_text_in_memory(
        {"id": "m-doc", "body": {"content": ""}},
        [{"name": "candidate_cv.doc", "contentType": "application/msword", "_raw_bytes": raw_doc}],
    )
    assert src == "candidate_cv.doc"
    assert "FastAPI Docker Kubernetes" in text


@pytest.mark.asyncio
async def test_cid_embedding_large_value_stream_and_send_failure_guard(mock_outlook_service):
    """Verify send_reply_email embeds referenced cid PNGs, fetch_attachments streams /$value, and failed sends stay unread."""
    mock_resp_ok = MagicMock(status_code=202, text="")
    with patch.object(mock_outlook_service, "_get_auth_headers", AsyncMock(return_value={"Authorization": "Bearer t"})), \
         patch.object(mock_outlook_service, "_graph_request", AsyncMock(return_value=mock_resp_ok)) as mock_req:
        sent = await mock_outlook_service.send_reply_email(
            "cand@example.com",
            "Report",
            '<img src="cid:icon-check" /><img src="cid:icon-book" />',
        )
        assert sent is True
        _, kwargs = mock_req.call_args
        atts = kwargs["json"]["message"]["attachments"]
        cids = {a["contentId"] for a in atts}
        assert cids == {"icon-check", "icon-book"}
        assert all(a["isInline"] is True for a in atts)

    # Large PDF (>3MB, missing contentBytes) + inline signature image filtering
    att_list_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "value": [
                {"id": "img-1", "name": "logo.png", "contentType": "image/png", "isInline": True},
                {"id": "pdf-1", "name": "Resume_Big.pdf", "contentType": "application/pdf", "isInline": False},
            ]
        },
    )
    val_stream_resp = MagicMock(status_code=200, content=b"%PDF-1.4 streamed binary content")
    with patch.object(mock_outlook_service, "_get_auth_headers", AsyncMock(return_value={"Authorization": "Bearer t"})), \
         patch.object(mock_outlook_service, "_graph_request", AsyncMock(side_effect=[att_list_resp, val_stream_resp])):
        atts = await mock_outlook_service.fetch_attachments("msg-big")
        assert len(atts) == 1
        assert atts[0]["name"] == "Resume_Big.pdf"
        assert atts[0]["_raw_bytes"] == b"%PDF-1.4 streamed binary content"

    # Failed send_reply_email must NOT mark message as read (prevents silent dropped applications)
    msg = {
        "id": "msg-fail-send",
        "subject": "AI Engineer Application",
        "from": {"emailAddress": {"address": "user@example.com", "name": "User"}},
        "hasAttachments": False,
        "body": {"contentType": "Text", "content": "Python PyTorch FastAPI Docker Senior Engineer with 5 years production AI experience."},
    }
    mock_orch = MagicMock()
    mock_orch.process = AsyncMock(return_value={"overall_score": 80, "executive_summary": "Good", "strengths": ["Python"], "skill_gaps": []})
    with patch("app.services.sharepoint_service.sharepoint_service.is_configured", return_value=False), \
         patch.object(mock_outlook_service, "send_reply_email", AsyncMock(return_value=False)), \
         patch.object(mock_outlook_service, "mark_message_as_read", AsyncMock(return_value=True)) as mock_read:
        res = await mock_outlook_service.process_candidate_message(msg, mock_orch)
        assert res["emailSent"] is False
        mock_read.assert_not_awaited()


def test_ai_client_rate_limit_configuration():
    """Verify GenAIClient disables hidden 70s SDK retry loop and sets safe 2.5s spacing + circuit breaker."""
    from app.ai.client import GenAIClient

    assert GenAIClient._min_request_gap == 2.5
    assert hasattr(GenAIClient, "_groq_unavailable")
    with patch("app.ai.client.MistralAsyncClient") as mock_mistral_cls:
        GenAIClient()
        assert mock_mistral_cls.called
        _, kwargs = mock_mistral_cls.call_args
        assert kwargs.get("max_retries") == 1


@pytest.mark.asyncio
async def test_self_reply_loop_ignored(mock_outlook_service):
    """Verify outbound Friction HR evaluation replies arriving in same inbox are ignored without running AI."""
    self_reply_msg = {
        "id": "msg-self-1",
        "subject": "Your Talent Evaluation & Roadmap: Ai Engineer",
        "from": {"emailAddress": {"address": "a.rehaan@sstlab.in", "name": "Ahmed Rehaan"}},
        "bodyPreview": "Friction Matcher AI Talent Suite",
        "hasAttachments": False,
        "body": {"content": "<div>Friction Matcher AI Talent Suite</div>"},
    }
    mock_orchestrator = MagicMock()
    with patch.object(mock_outlook_service, "mark_message_as_read", AsyncMock(return_value=True)) as mock_read:
        res = await mock_outlook_service.process_candidate_message(self_reply_msg, mock_orchestrator)
        assert res["status"] == "ignored_system_email"
        assert res["reason"] == "self_evaluation_reply"
        mock_read.assert_awaited_once_with("msg-self-1")
        mock_orchestrator.process.assert_not_called()


def test_large_document_chunker_zero_truncation():
    """Verify 25,000+ char resumes and JDs preserve bottom skills/experience via semantic chunking and filter EEO noise."""
    from app.utils.document_chunker import chunk_document, extract_core_sections

    # Synthetic 25,000+ char JD with trailing EEO boilerplate + skills hidden far past 15k chars
    filler = "Detailed architecture collaboration across distributed product teams and cross-functional planning.\n" * 240
    large_jd = (
        "### Overview\nEnterprise AI Engineer opening.\n\n"
        f"### Background Context\n{filler}\n\n"
        "### Requirements\nRequired: 5+ years Python, PyTorch, Kubernetes, and Azure ML.\n\n"
        "### Legal Notice\nWe are an Equal Opportunity Employer without regard to race, color, religion, sex, "
        "national origin, age, disability, protected veteran status, or reasonable accommodation policies.\n"
    )
    assert len(large_jd) > 20000

    chunks = chunk_document(large_jd, doc_type="jd", chunk_size=8000, overlap=300)
    combined_chunks = "\n".join(c["text"] for c in chunks)
    assert len(chunks) >= 3
    assert "PyTorch, Kubernetes, and Azure ML" in combined_chunks
    assert "Equal Opportunity Employer" not in combined_chunks

    core_view = extract_core_sections(large_jd, doc_type="jd", max_chars=4000)
    assert "PyTorch, Kubernetes, and Azure ML" in core_view
    assert len(core_view) <= 4000


def test_domain_mismatch_unparseable_and_dynamic_domain_rendering(mock_outlook_service):
    """Verify domain_mismatch, unparseable_jd, and dynamic open-domain labels render Frontend Zinc templates."""
    mismatch_html = mock_outlook_service.generate_professional_html_report(
        candidate_name="Alex Mercer",
        target_role="AI Engineer",
        analysis={
            "status": "domain_mismatch",
            "resume_domain": "Corporate Legal Counsel",
            "jd_domain": "AI Engineer",
            "overall_score": 0,
            "message": "Transitioning from Corporate Law to AI Engineering requires foundational Python & ML coursework.",
        },
        matched_from_sharepoint=True,
        sharepoint_source_file="ai_engineer.pdf",
    )
    assert "Cross-Domain Career Transition Detected" in mismatch_html
    assert "Corporate Legal Counsel" in mismatch_html
    assert "Needs Targeted Upskilling" not in mismatch_html
    assert "cid:icon-alert-triangle" in mismatch_html

    unparseable_html = mock_outlook_service.generate_professional_html_report(
        candidate_name="Alex Mercer",
        target_role="Open Application",
        analysis={
            "status": "unparseable_jd",
            "overall_score": None,
            "message": "Could not extract explicit job requirements.",
        },
    )
    assert "Additional Role Details Needed for Scoring" in unparseable_html
    assert "Needs Targeted Upskilling" not in unparseable_html
    assert "cid:icon-info" in unparseable_html

    dyn_label = mock_outlook_service._format_domain_display({
        "domain_analysis": {
            "resume_domain": "unknown",
            "jd_domain": "unknown",
            "detected_role_domain": "Cybersecurity / Cloud IAM",
        }
    })
    assert dyn_label == "Cybersecurity / Cloud IAM"


@pytest.mark.asyncio
async def test_hybrid_open_domain_orchestrator_non_hardcoded_role():
    """Verify non-hardcoded cybersecurity/IAM JD routes through OpenDomainExtractor seamlessly in orchestrator."""
    from app.ai.orchestrator import DeterministicOrchestrator

    cyber_jd = (
        "Role: Principal Cybersecurity IAM Architect\n"
        "Requirements:\n"
        "- Minimum 4 years designing Zero Trust identity architectures with Okta and SailPoint\n"
        "- Hands-on SOC threat hunting using CrowdStrike Falcon and Splunk SIEM\n"
        "- Cloud IAM federation via OIDC, SAML 2.0, and HashiCorp Vault\n"
    )
    cyber_resume = (
        "Security Architect with 5 years experience deploying Zero Trust Okta IAM, OIDC/SAML 2.0, "
        "and HashiCorp Vault enterprise secrets management."
    )
    mock_od_res = {
        "domain": "Cybersecurity / Identity & Access Management",
        "requirements": [
            {"name": "Zero Trust Architecture", "category": "domain_experience", "importance": "must_have"},
            {"name": "Okta IAM", "category": "tool", "importance": "must_have"},
            {"name": "CrowdStrike Falcon", "category": "tool", "importance": "preferred"},
            {"name": "Splunk SIEM", "category": "tool", "importance": "preferred"},
        ],
    }
    mock_holistic = {
        "executive_summary": "Strong Zero Trust & Okta match.",
        "ats_optimization": {"keywords": ["Splunk SIEM", "CrowdStrike Falcon"], "phrasing": [], "formatting_tips": []},
        "seniority_alignment": {"summary": "5 yrs meets 4+ yrs required.", "recommendation": "Highlight SIEM projects."},
    }
    mock_roadmap = {"title": "Cybersecurity Bridge", "weeks": []}

    orch = DeterministicOrchestrator()
    with patch("app.ai.client.GenAIClient.generate_structured_content", AsyncMock(return_value=mock_od_res)), \
         patch("app.ai.explainer.Phase3Explainer.generate_holistic_insights", AsyncMock(return_value=mock_holistic)), \
         patch("app.ai.explainer.Phase3Explainer.generate_roadmap", AsyncMock(return_value=mock_roadmap)):
        result = await orch.process({
            "resume": cyber_resume,
            "jd_text": cyber_jd,
            "enableOpenDomain": True,
        })

    assert result.get("status") != "unparseable_jd"
    assert result["overall_score"] is not None and result["overall_score"] > 50
    assert result["domain_analysis"].get("detected_role_domain") == "Cybersecurity / Identity & Access Management"
    assert "CrowdStrike Falcon" in result["skill_gaps"]
    assert "Okta IAM" in result["strengths"]
    assert hasattr(__import__("app.ai.client", fromlist=["GenAIClient"]).GenAIClient, "_mistral_cooldown_until")


def test_prose_false_positive_removal_and_fractional_seniority(mock_outlook_service):
    """Verify open-domain deterministic fallback excludes prose noise (Architecture/Troubleshooting) & renders fractional years."""
    from app.utils.skill_extractor import extract_open_domain_skills

    ai_jd_prose = "Architect scalable system architecture, cloud streaming pipelines, and model troubleshooting in Python, Docker, SQL, and Kubernetes."
    extracted = extract_open_domain_skills(ai_jd_prose)
    assert "Architecture" not in extracted
    assert "Troubleshooting" not in extracted
    assert "Streaming" not in extracted
    assert {"Python", "Docker", "SQL", "Kubernetes"}.issubset(set(extracted))

    html_out = mock_outlook_service.generate_professional_html_report(
        candidate_name="Aarav Sharma",
        target_role="Ai Engineer",
        analysis={
            "overall_score": 52,
            "executive_summary": "Strong Python & Docker skills.",
            "strengths": ["Python", "Docker"],
            "skill_gaps": ["Azure", "Kubernetes"],
            "seniority_analysis": {
                "your_level": "Entry",
                "required_level": "Mid",
                "years_experience": 1.3,
                "required_years": 3,
                "alignment_status": "minor_gap",
                "alignment_badge": "MINOR GAP",
            },
        },
    )
    assert "1.3 yrs (Entry)" in html_out





