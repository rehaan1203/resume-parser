"""
Microsoft Outlook / Azure AD Integration Service for Friction Matcher.

Provides autonomous, in-memory processing of candidate emails and resume attachments
without saving files to disk (zero disk I/O, strict privacy preservation).
"""

import asyncio
import base64
import html
import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
import msal
from bs4 import BeautifulSoup

from app.config import settings
from app.utils.logger import logger

_EMAIL_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "email_icons"
_ICON_B64_CACHE: Dict[str, str] = {}


def _load_email_icon_b64(icon_id: str) -> Optional[str]:
    """Load and cache base64-encoded PNG icon bytes for CID email embedding."""
    if icon_id in _ICON_B64_CACHE:
        return _ICON_B64_CACHE[icon_id]
    icon_path = _EMAIL_ICONS_DIR / f"{icon_id}.png"
    if not icon_path.is_file():
        return None
    encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    _ICON_B64_CACHE[icon_id] = encoded
    return encoded


def _cid_icon(icon_id: str, size: int = 16, alt: str = "") -> str:
    """Render an Outlook-safe inline CID image tag matching Frontend Lucide icons."""
    safe_id = html.escape(icon_id, quote=True)
    safe_alt = html.escape(alt, quote=True)
    return (
        f'<img src="cid:{safe_id}" width="{size}" height="{size}" alt="{safe_alt}" '
        f'style="display: inline-block; width: {size}px; height: {size}px; vertical-align: -3px; '
        f'border: 0; outline: none; text-decoration: none;" />'
    )


def _mask_email(addr: str) -> str:
    """Mask email local-part before logging so candidate PII stays redacted."""
    clean = (addr or "").strip()
    if "@" not in clean:
        return "***"
    local, domain = clean.split("@", 1)
    prefix = local[:2] if len(local) > 2 else local[:1]
    return f"{prefix}***@{domain}"


class OutlookService:
    """Service for interacting with Microsoft Graph API and processing candidate emails."""

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        mailbox_email: Optional[str] = None,
    ):
        self.tenant_id = settings.azure_tenant_id if tenant_id is None else tenant_id
        self.client_id = settings.azure_client_id if client_id is None else client_id
        self.client_secret = settings.azure_client_secret if client_secret is None else client_secret
        self.mailbox_email = settings.azure_outlook_email if mailbox_email is None else mailbox_email
        self._msal_app: Optional[msal.ConfidentialClientApplication] = None
        self._cached_token: Optional[str] = None
        self._poller_paused: bool = False
        self._token_lock: Optional[asyncio.Lock] = None
        self._poll_lock: Optional[asyncio.Lock] = None
        self._graph_client: Optional[httpx.AsyncClient] = None

    def _get_token_lock(self) -> asyncio.Lock:
        if self._token_lock is None:
            self._token_lock = asyncio.Lock()
        return self._token_lock

    def _get_poll_lock(self) -> asyncio.Lock:
        if self._poll_lock is None:
            self._poll_lock = asyncio.Lock()
        return self._poll_lock

    def _get_graph_client(self) -> httpx.AsyncClient:
        """Return a shared persistent HTTP client for Microsoft Graph calls."""
        if self._graph_client is None or self._graph_client.is_closed:
            self._graph_client = httpx.AsyncClient(
                timeout=20.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._graph_client

    async def _graph_request(
        self,
        method: str,
        url: str,
        max_attempts: int = 3,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute a Graph HTTP call with shared connection pooling and 429/503 Retry-After backoff."""
        client = self._get_graph_client()
        for attempt in range(1, max_attempts + 1):
            resp = await client.request(method, url, **kwargs)
            if resp.status_code not in (429, 503, 504) or attempt == max_attempts:
                return resp
            retry_after_raw = resp.headers.get("Retry-After")
            try:
                delay = min(float(retry_after_raw), 15.0) if retry_after_raw else float(2 ** attempt)
            except ValueError:
                delay = float(2 ** attempt)
            logger.warning(
                f"Microsoft Graph transient {resp.status_code} on {method} {url.split('?')[0]}; "
                f"retrying in {delay:.1f}s (attempt {attempt}/{max_attempts})."
            )
            await asyncio.sleep(delay)
        return resp

    async def close(self) -> None:
        """Close the shared Graph HTTP client pool gracefully during shutdown."""
        if self._graph_client is not None and not self._graph_client.is_closed:
            try:
                await self._graph_client.aclose()
            except Exception:
                pass
            self._graph_client = None

    def pause_poller(self) -> None:
        """Pause background inbox polling at runtime (e.g., during dedicated frontend sessions)."""
        self._poller_paused = True
        logger.info("Outlook background poller paused.")

    def resume_poller(self) -> None:
        """Resume background inbox polling at runtime."""
        self._poller_paused = False
        logger.info("Outlook background poller resumed.")

    def is_poller_paused(self) -> bool:
        """Return whether background inbox polling is currently paused."""
        return self._poller_paused

    def is_configured(self) -> bool:
        """Verify whether all required Azure credentials and mailbox settings are provided."""
        return bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.mailbox_email
        )

    def _get_msal_client(self) -> msal.ConfidentialClientApplication:
        """Create or return the cached MSAL ConfidentialClientApplication."""
        if not self._msal_app:
            if not (self.tenant_id and self.client_id and self.client_secret):
                raise ValueError("Azure tenant_id, client_id, and client_secret must be configured.")
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=authority,
            )
        return self._msal_app

    async def acquire_token(self) -> str:
        """Acquire an OAuth 2.0 Bearer token asynchronously without blocking the event loop."""
        async with self._get_token_lock():
            msal_app = self._get_msal_client()
            scopes = ["https://graph.microsoft.com/.default"]

            # Run synchronous MSAL cache lookup & AAD HTTP calls on a worker thread
            result = await asyncio.to_thread(msal_app.acquire_token_silent, scopes, account=None)
            if not result:
                result = await asyncio.to_thread(msal_app.acquire_token_for_client, scopes=scopes)

            if result and "access_token" in result:
                self._cached_token = result["access_token"]
                return self._cached_token

            error_desc = (result or {}).get("error_description", (result or {}).get("error", "Unknown MSAL error"))
            logger.error(f"Failed to acquire Microsoft Graph token: {error_desc}")
            raise PermissionError(f"Microsoft Graph authentication failed: {error_desc}")

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Generate HTTP Authorization headers with the bearer token."""
        token = await self.acquire_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Test authentication and verify mailbox accessibility."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "Outlook credentials not fully configured in environment.",
                "mailbox": self.mailbox_email,
            }

        try:
            headers = await self._get_auth_headers()
            url = f"{self.GRAPH_BASE_URL}/users/{self.mailbox_email}"
            resp = await self._graph_request("GET", url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "mailbox": self.mailbox_email,
                    "displayName": data.get("displayName"),
                    "mail": data.get("mail") or data.get("userPrincipalName"),
                }
            return {
                "success": False,
                "statusCode": resp.status_code,
                "error": resp.text,
                "mailbox": self.mailbox_email,
            }
        except Exception as e:
            logger.error(f"Outlook test_connection error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "mailbox": self.mailbox_email,
            }

    async def fetch_unread_candidate_emails(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch unread emails from the mailbox inbox (supports @odata.nextLink pagination up to limit).
        Orders by received date descending.
        """
        if not self.is_configured():
            logger.warning("Outlook service is not configured. Cannot fetch emails.")
            return []

        headers = await self._get_auth_headers()
        next_url: Optional[str] = (
            f"{self.GRAPH_BASE_URL}/users/{self.mailbox_email}/mailFolders/Inbox/messages"
            f"?$filter=isRead eq false&$orderby=receivedDateTime desc&$top={limit}"
            f"&$select=id,subject,bodyPreview,body,from,receivedDateTime,hasAttachments"
        )
        collected: List[Dict[str, Any]] = []

        while next_url and len(collected) < limit:
            resp = await self._graph_request("GET", next_url, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Error fetching unread emails ({resp.status_code}): {resp.text}")
                break
            data = resp.json()
            batch = data.get("value", [])
            collected.extend(batch)
            next_url = data.get("@odata.nextLink")

        return collected[:limit]

    async def fetch_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Fetch attachments for a message (follows @odata.nextLink, filters inline signature images,
        and streams binary bytes via /$value for attachments >3 MB where Graph omits contentBytes).
        """
        headers = await self._get_auth_headers()
        next_url: Optional[str] = f"{self.GRAPH_BASE_URL}/users/{self.mailbox_email}/messages/{message_id}/attachments"
        filtered_attachments: List[Dict[str, Any]] = []

        while next_url:
            resp = await self._graph_request("GET", next_url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Could not fetch attachments for {message_id}: {resp.status_code}")
                break
            data = resp.json()
            for att in data.get("value", []):
                name = (att.get("name") or "").lower()
                is_inline = bool(att.get("isInline", False))
                # Skip inline email signature/logo images to avoid wasted RAM/bandwidth
                if is_inline and name.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp")):
                    continue

                odata_type = str(att.get("@odata.type") or "")
                is_doc = (
                    name.endswith((".pdf", ".docx", ".doc", ".txt"))
                    or "pdf" in (att.get("contentType") or "").lower()
                    or "word" in (att.get("contentType") or "").lower()
                    or "text/plain" in (att.get("contentType") or "").lower()
                )
                max_att_bytes = getattr(settings, "max_download_size_bytes", 15 * 1024 * 1024)
                reported_size = att.get("size") or 0
                if reported_size and reported_size > max_att_bytes:
                    logger.warning(f"Skipping oversized attachment '{att.get('name')}' ({reported_size} bytes > {max_att_bytes}).")
                    continue

                # Large Graph fileAttachments (>3MB) omit contentBytes; stream raw bytes via /$value
                if is_doc and not att.get("contentBytes") and att.get("id") and "referenceAttachment" not in odata_type:
                    val_url = f"{self.GRAPH_BASE_URL}/users/{self.mailbox_email}/messages/{message_id}/attachments/{att['id']}/$value"
                    val_resp = await self._graph_request("GET", val_url, headers=headers)
                    if val_resp.status_code == 200 and val_resp.content:
                        if len(val_resp.content) > max_att_bytes:
                            logger.warning(f"Skipping oversized /$value attachment '{att.get('name')}' ({len(val_resp.content)} bytes).")
                            continue
                        att["_raw_bytes"] = val_resp.content
                        logger.info(f"Streamed large attachment via /$value: {att.get('name')} ({len(val_resp.content)} bytes)")

                filtered_attachments.append(att)

            next_url = data.get("@odata.nextLink")

        return filtered_attachments

    def extract_resume_text_in_memory(
        self,
        message: Dict[str, Any],
        attachments: List[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """
        Extract resume text strictly in-memory from attachments (PDF, DOCX, TXT)
        or from the email body if no attachment is attached. Zero disk writes.

        Returns:
            Tuple of (extracted_text, source_name)
        """
        # 1. Search for attachment-based resume
        for att in attachments:
            name = att.get("name", "").lower()
            content_type = att.get("contentType", "").lower()
            raw_bytes: Optional[bytes] = att.get("_raw_bytes")

            if raw_bytes is None:
                content_bytes_b64 = att.get("contentBytes")
                if not content_bytes_b64:
                    continue
                try:
                    raw_bytes = base64.b64decode(content_bytes_b64)
                except Exception as e:
                    logger.warning(f"Failed to decode base64 attachment {name}: {e}")
                    continue

            # PDF Extraction (In-Memory)
            if name.endswith(".pdf") or "pdf" in content_type:
                text = self._extract_pdf_in_memory(raw_bytes)
                if len(text.strip()) >= 50:
                    logger.info(f"Extracted {len(text)} chars from in-memory PDF: {name}")
                    return text.strip(), att.get("name", "resume.pdf")

            # DOCX Extraction (In-Memory)
            elif name.endswith(".docx") or "wordprocessingml" in content_type:
                text = self._extract_docx_in_memory(raw_bytes)
                if len(text.strip()) >= 50:
                    logger.info(f"Extracted {len(text)} chars from in-memory DOCX: {name}")
                    return text.strip(), att.get("name", "resume.docx")

            # Legacy binary .doc fallback (printable UTF-16LE / ASCII text scan)
            elif name.endswith(".doc") or "application/msword" in content_type:
                text = self._extract_legacy_doc_fallback(raw_bytes)
                if len(text.strip()) >= 80:
                    logger.info(f"Extracted {len(text)} chars from legacy .doc attachment: {name}")
                    return text.strip(), att.get("name", "resume.doc")

            # Plain text attachment
            elif name.endswith(".txt") or "text/plain" in content_type:
                try:
                    text = raw_bytes.decode("utf-8", errors="ignore")
                    if len(text.strip()) >= 50:
                        return text.strip(), att.get("name", "resume.txt")
                except Exception as e:
                    logger.warning(f"Failed to decode txt attachment {name}: {e}")

        # 2. Fallback: Parse resume text directly from email body
        body_obj = message.get("body", {})
        body_content = body_obj.get("content", "")
        body_type = body_obj.get("contentType", "Text")

        clean_body = ""
        if body_type.lower() == "html":
            soup = BeautifulSoup(body_content, "html.parser")
            clean_body = soup.get_text(separator="\n").strip()
        else:
            clean_body = body_content.strip()

        if len(clean_body) >= 60:
            logger.info("Extracted resume text directly from email body")
            return clean_body, "email_body"

        return "", "none"

    async def extract_resume_text_in_memory_async(
        self,
        message: Dict[str, Any],
        attachments: List[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """Run CPU-bound in-memory PDF/DOCX extraction on a worker thread to keep the event loop non-blocking."""
        return await asyncio.to_thread(self.extract_resume_text_in_memory, message, attachments)

    def _extract_pdf_in_memory(self, raw_bytes: bytes) -> str:
        """Extract text from raw PDF bytes using pdfplumber with PyPDF2 fallback."""
        text_parts = []
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts:
                return "\n".join(text_parts)
        except Exception as e:
            logger.warning(f"pdfplumber in-memory extraction encountered error: {e}. Trying PyPDF2...")

        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_parts.append(extracted)
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"PyPDF2 in-memory extraction failed: {e}")

        return ""

    def _extract_docx_in_memory(self, raw_bytes: bytes) -> str:
        """Extract text from raw DOCX bytes using python-docx."""
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw_bytes))
            parts = []
            for p in doc.paragraphs:
                if p.text:
                    parts.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        parts.append(row_text)
            return "\n".join(parts)
        except Exception as e:
            logger.error(f"python-docx in-memory extraction failed: {e}")
            return ""

    @staticmethod
    def _extract_legacy_doc_fallback(raw_bytes: bytes) -> str:
        """Best-effort printable text scan for legacy binary .doc OLE documents without touching disk."""
        if not raw_bytes:
            return ""
        # Try UTF-16LE runs first (Word binary stores Unicode streams in UTF-16LE)
        try:
            u16 = raw_bytes.decode("utf-16le", errors="ignore")
            u16_runs = re.findall(r"[A-Za-z0-9][A-Za-z0-9\s\.,;:\-\(\)/\+\#&]{15,}", u16)
            u16_text = "\n".join(r.strip() for r in u16_runs if sum(c.isalpha() for c in r) >= 8)
            if len(u16_text) >= 80:
                return u16_text
        except Exception:
            pass
        ascii_runs = re.findall(rb"[A-Za-z0-9][A-Za-z0-9\s\.,;:\-\(\)/\+\#&]{15,}", raw_bytes)
        return "\n".join(r.decode("ascii", errors="ignore").strip() for r in ascii_runs if sum(c.isalpha() for c in r.decode("ascii", errors="ignore")) >= 8)

    def infer_target_role_and_jd(self, subject: str, body_text: str) -> str:
        """
        Infer the target role or job context from the email subject line or body.
        Constructs a clean target JD context for the orchestrator.
        """
        combined = f"{subject} {body_text[:300]}"

        # Regex patterns to capture job title
        patterns = [
            r"(?:application|applying|applying for|applied for|role of|job application:?)\s*(?:for|as)?\s*([A-Za-z0-9\s\-\/\#\+]{3,40}?)(?:[\.\,\-\|\(]|$)",
            r"(?:role|position|profile)\s*:\s*([A-Za-z0-9\s\-\/\#\+]{3,40}?)(?:[\.\,\-\|\(]|$)",
            r"([A-Za-z0-9\s\-\/\#\+]{3,35})\s*(?:-|–|—|\|)\s*(?:resume|cv|application)",
            r"(?:resume|cv)\s*(?:-|–|—|\|)\s*([A-Za-z0-9\s\-\/\#\+]{3,35})",
        ]

        target_title = None
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                candidate_title = match.group(1).strip()
                # Exclude trivial non-title words
                if len(candidate_title) > 3 and not any(
                    w in candidate_title.lower() for w in ["resume", "application", "hello", "dear", "hiring", "job", "please find"]
                ):
                    target_title = candidate_title
                    break

        if target_title:
            return (
                f"Job Title: {target_title}.\n"
                f"Target Role: {target_title}.\n"
                f"Requirements: Proven professional competence and domain expertise in {target_title}. "
                f"Demonstrated execution of core industry responsibilities, technical standards, and domain workflows."
            )

        # Generic domain-adaptable fallback JD
        return (
            "Job Title: Domain Professional / Specialist.\n"
            "Requirements: Comprehensive proficiency in domain-specific competencies, industry best practices, "
            "problem-solving capabilities, and verified technical execution standards."
        )

    def extract_candidate_name(
        self,
        resume_text: str,
        attachment_name: Optional[str] = None,
        fallback_sender: Optional[str] = None,
    ) -> str:
        """
        Extract the actual candidate's real name with high accuracy.
        1. Analyzes the top lines of the resume text before sections/contact info.
        2. Heuristic fallback from attachment filename (e.g. 'aarav-sharma-resume.pdf' -> 'Aarav Sharma').
        3. Fallback to email sender display name if no candidate name is detectable.
        """
        # 1. Parse top lines of resume text
        if resume_text:
            lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
            for line in lines[:8]:
                # Clean punctuation at ends
                cleaned = line.strip(" -–—:|*•\t")
                # Exclude lines with contact / URL markers
                if any(x in cleaned.lower() for x in ["@", "http", "www.", ".com", "+", "phone", "email", "github", "linkedin", "curriculum", "resume", "profile", "summary"]):
                    continue
                # Exclude long descriptions
                words = cleaned.split()
                if 2 <= len(words) <= 4:
                    # Check if all words are alphabetic
                    if all(re.match(r"^[A-Za-z\.\'\-]+$", w) for w in words):
                        # Ensure not section headers or job titles
                        header_blacklist = {
                            "work", "experience", "education", "skills", "projects", "certifications",
                            "objective", "career", "technical", "summary", "contact", "developer",
                            "engineer", "architect", "lead", "senior", "junior", "manager",
                            "consultant", "analyst", "intern", "specialist", "administrator",
                            "designer", "programmer", "officer", "executive", "full", "stack",
                            "backend", "frontend", "devops", "cloud", "software"
                        }
                        if not any(w.lower() in header_blacklist for w in words):
                            return " ".join(w.capitalize() for w in words)

        # 2. Heuristic from attachment filename
        if attachment_name and attachment_name not in ["email_body", "none"]:
            stem = re.sub(r"\.(pdf|docx|txt|doc)$", "", attachment_name, flags=re.IGNORECASE)
            # Remove common resume stopwords
            stem = re.sub(r"(?i)[-_]?(resume|cv|curriculum|vitae|profile|final|updated|v\d+)[-_]?", " ", stem)
            # Replace underscores, hyphens, dots with spaces
            cleaned_stem = re.sub(r"[-_.]+", " ", stem).strip()
            words = cleaned_stem.split()
            if 2 <= len(words) <= 4 and all(re.match(r"^[A-Za-z]+$", w) for w in words):
                return " ".join(w.capitalize() for w in words)

        # 3. Fallback to sender display name
        if fallback_sender and fallback_sender.lower() not in ["candidate", "unknown", "none", ""]:
            return fallback_sender.strip()

        return "Candidate"

    async def mark_message_as_read(self, message_id: str) -> bool:
        """Mark the message as read in Microsoft Graph to guarantee idempotency."""
        headers = await self._get_auth_headers()
        url = f"{self.GRAPH_BASE_URL}/users/{self.mailbox_email}/messages/{message_id}"
        payload = {"isRead": True}

        resp = await self._graph_request("PATCH", url, headers=headers, json=payload)
        if resp.status_code in [200, 204]:
            logger.info(f"Marked message {message_id} as read.")
            return True
        logger.warning(f"Failed to mark message {message_id} as read: {resp.status_code}")
        return False

    async def send_reply_email(
        self,
        to_address: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """
        Send a Frontend-aligned HTML evaluation response email with inline CID vector icons
        back to the candidate via Microsoft Graph.
        """
        if not self.is_configured():
            logger.warning("Outlook service not configured. Cannot send email.")
            return False

        headers = await self._get_auth_headers()
        url = f"{self.GRAPH_BASE_URL}/users/{self.mailbox_email}/sendMail"

        # Auto-attach any CID icons referenced in html_body as inline Graph attachments
        cid_ids = sorted(set(re.findall(r'src=["\']cid:([a-z0-9\-]+)["\']', html_body, flags=re.IGNORECASE)))
        inline_attachments: List[Dict[str, Any]] = []
        for cid_id in cid_ids:
            b64_png = _load_email_icon_b64(cid_id)
            if b64_png:
                inline_attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": f"{cid_id}.png",
                    "contentType": "image/png",
                    "isInline": True,
                    "contentId": cid_id,
                    "contentBytes": b64_png,
                })

        message_obj: Dict[str, Any] = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_address,
                    }
                }
            ],
        }
        if inline_attachments:
            message_obj["attachments"] = inline_attachments

        email_payload = {
            "message": message_obj,
            "saveToSentItems": True,
        }

        resp = await self._graph_request("POST", url, headers=headers, json=email_payload)
        if resp.status_code in [200, 202]:
            logger.info(f"Successfully sent verdict email to candidate: {_mask_email(to_address)}")
            return True
        logger.error(f"Failed to send email to {_mask_email(to_address)} ({resp.status_code}): {resp.text}")
        return False

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Allow only safe http/https URLs in HTML links."""
        clean = str(url or "").strip()
        if clean.startswith(("https://", "http://")):
            return html.escape(clean, quote=True)
        return "#"

    @staticmethod
    def _derive_readable_link_title(url: str, fallback_context: str = "") -> str:
        """Convert a raw URL into a clean, human-readable resource title."""
        from urllib.parse import parse_qs, unquote, urlparse

        clean_url = str(url or "").strip()
        if not clean_url or clean_url == "#":
            return fallback_context or "Learning Resource"

        try:
            parsed = urlparse(clean_url)
            host = (parsed.hostname or "").lower().replace("www.", "")
            qs = parse_qs(parsed.query)
            segments = [s for s in parsed.path.split("/") if s and s.lower() not in ("en-us", "docs", "learn", "training", "modules", "concepts", "stable", "tutorial")]

            # Extract human-friendly topic from query string if present (e.g. ?query=microsoft+azure or ?terms=...)
            topic = ""
            for q_key in ("query", "terms", "q", "search"):
                if q_key in qs and qs[q_key]:
                    topic = unquote(qs[q_key][0]).replace("+", " ").strip()
                    break

            if not topic and segments:
                generic_slugs = {"watch", "embed", "courses", "search", "index"}
                ambiguous_tail = {"overview", "introduction", "quickstart", "getting-started", "get-started", "about", "home"}
                cleaned_segs = [
                    re.sub(r"\.(html?|asp|php)$", "", unquote(s), flags=re.IGNORECASE)
                    for s in segments
                ]
                last_seg = cleaned_segs[-1]
                if last_seg.lower() not in generic_slugs:
                    if last_seg.lower() in ambiguous_tail and len(cleaned_segs) >= 2:
                        # Include parent service segment so ".../azure-monitor/overview" != ".../security/overview"
                        parent = cleaned_segs[-2]
                        if parent.lower() in {"fundamentals", "basics"} and len(cleaned_segs) >= 3:
                            topic_raw = f"{cleaned_segs[-3]} {parent} {last_seg}"
                        else:
                            topic_raw = f"{parent} {last_seg}"
                        topic = re.sub(r"[-_]+", " ", topic_raw).strip()
                    else:
                        topic = re.sub(r"[-_]+", " ", last_seg).strip()

            # Clean common generic topic noise
            if topic:
                acronyms = {"html", "css", "js", "sql", "ml", "ai", "api", "aws", "gcp", "ci/cd", "sdk", "rbac", "iam", "rag", "kql", "sas", "llm", "oauth", "jwt"}
                brand_map = {
                    "openai": "OpenAI",
                    "chatgpt": "ChatGPT",
                    "langchain": "LangChain",
                    "langgraph": "LangGraph",
                    "fastapi": "FastAPI",
                    "github": "GitHub",
                    "pytorch": "PyTorch",
                    "postgresql": "PostgreSQL",
                    "devops": "DevOps",
                }

                def _fmt_token(tok: str) -> str:
                    tl = tok.lower()
                    if tl in acronyms:
                        return tok.upper()
                    if tl in brand_map:
                        return brand_map[tl]
                    return tok.capitalize()

                formatted_words = []
                for w in topic.split():
                    if "-" in w and w.lower() not in brand_map and w.lower() not in acronyms:
                        formatted_words.append("-".join(_fmt_token(p) for p in w.split("-") if p))
                    else:
                        formatted_words.append(_fmt_token(w))
                topic = " ".join(formatted_words)

            # Map domain prefix
            if "coursera.org" in host:
                prefix = "Coursera"
            elif "learn.microsoft.com" in host or "microsoft.com" in host:
                prefix = "Microsoft Learn"
            elif "langchain" in host or "langgraph" in host:
                prefix = "LangChain Docs"
            elif "kubernetes.io" in host:
                prefix = "Kubernetes Docs"
            elif "developer.mozilla.org" in host:
                prefix = "MDN Web Docs"
            elif "w3schools.com" in host:
                prefix = "W3Schools"
            elif "youtube.com" in host or "youtu.be" in host:
                prefix = "YouTube Video"
                if fallback_context:
                    topic = fallback_context
                elif not topic:
                    topic = "Guided Walkthrough"
            elif "freecodecamp.org" in host:
                prefix = "freeCodeCamp"
            elif "scikit-learn.org" in host:
                prefix = "Scikit-learn Docs"
            elif "developers.google.com" in host:
                prefix = "Google ML Docs"
            elif "minikube" in host:
                prefix = "Minikube Docs"
            elif "css-tricks.com" in host:
                prefix = "CSS-Tricks"
            else:
                parts = [p for p in host.split(".") if p]
                generic_subs = {"docs", "reference", "api", "developer", "learn", "cloud"}
                if len(parts) >= 3 and parts[0] in generic_subs:
                    prefix = f"{parts[-2].capitalize()} Docs"
                else:
                    prefix = parts[0].capitalize() if parts else "Resource"

            if topic and len(topic) > 2:
                title = f"{prefix}: {topic}"
            elif fallback_context:
                title = f"{prefix}: {fallback_context}"
            else:
                title = f"{prefix} Guide"

            if len(title) <= 56:
                return title
            sliced = title[:53]
            if " " in sliced:
                word_bound = sliced.rsplit(" ", 1)[0]
                if len(word_bound) > len(prefix) + 4:
                    sliced = word_bound
            return sliced.rstrip(" ,:-+&") + "..."
        except Exception:
            return fallback_context or "Official Documentation"

    @staticmethod
    def _derive_platform_from_url(url: str) -> str:
        """Identify clean platform label for a URL."""
        u = (url or "").lower()
        if "coursera.org" in u:
            return "Coursera"
        if "youtube.com" in u or "youtu.be" in u:
            return "YouTube"
        if "learn.microsoft.com" in u:
            return "Microsoft Learn"
        if "kubernetes.io" in u:
            return "Kubernetes"
        if "developer.mozilla.org" in u:
            return "MDN Docs"
        if "w3schools.com" in u:
            return "W3Schools"
        if "freecodecamp.org" in u:
            return "freeCodeCamp"
        if "scikit-learn.org" in u:
            return "Scikit-learn"
        return "Official Docs"

    @staticmethod
    def _format_domain_display(analysis: Dict[str, Any]) -> str:
        """Resolve readable, single-line domain label (preferring dynamic open-domain label when detected)."""
        display_map = {
            "software_engineering": "Software Eng",
            "data_science": "AI / ML",
            "product": "Product Mgmt",
            "legal": "Legal",
            "finance": "Finance",
            "marketing": "Marketing",
            "sales": "Sales",
            "hr": "Human Resources",
            "healthcare": "Healthcare",
            "trades": "Skilled Trades",
            "unknown": "General Professional",
        }
        domain_info = analysis.get("domain_analysis") or analysis.get("domainAnalysis") or {}
        if isinstance(domain_info, dict):
            dyn_dom = domain_info.get("detected_role_domain")
            res_dom = domain_info.get("resume_domain")
            jd_dom = domain_info.get("jd_domain")
            if dyn_dom and (res_dom == "unknown" or jd_dom == "unknown"):
                return str(dyn_dom)[:48]
            if res_dom and jd_dom and res_dom != jd_dom and res_dom != "unknown" and jd_dom != "unknown":
                res_lbl = display_map.get(res_dom, str(res_dom).replace("_", " ").title())
                jd_lbl = display_map.get(jd_dom, str(jd_dom).replace("_", " ").title())
                return f"{res_lbl} -> {jd_lbl}"
            if res_dom and res_dom != "unknown":
                return display_map.get(res_dom, str(res_dom).replace("_", " ").title())

        top_dom = analysis.get("resume_domain") or analysis.get("resumeDomain")
        if top_dom:
            return display_map.get(top_dom, str(top_dom).replace("_", " ").title())
        return "General Professional"

    def _linkify_resource_html(self, resource_item: Any, fallback_context: str = "") -> str:
        """Convert a markdown link, URL string, or resource dict into a crisp Frontend-styled pill link."""
        pill_style = (
            "display: inline-block; padding: 3px 10px; margin: 2px 4px 2px 0; "
            "background-color: #FFFFFF; border: 1px solid #D4D4D8; border-radius: 6px; "
            "color: #18181B; text-decoration: none; font-size: 12px; font-weight: 600; "
            "white-space: nowrap; max-width: 100%;"
        )
        if isinstance(resource_item, dict):
            raw_url = str(resource_item.get("url") or resource_item.get("link") or "")
            raw_title = str(resource_item.get("title") or resource_item.get("name") or "")
            if raw_title.startswith("http") or not raw_title:
                raw_title = self._derive_readable_link_title(raw_url, fallback_context)
            title = html.escape(raw_title)
            url = self._sanitize_url(raw_url)
            if url != "#":
                return f'<a href="{url}" target="_blank" class="fm-pill" style="{pill_style}">{title} &rarr;</a>'
            return f'<span class="fm-muted" style="color: #52525B; font-size: 12px;">{title}</span>'

        text = str(resource_item or "").strip()
        if not text:
            return ""

        md_match = re.search(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", text)
        if md_match:
            raw_lbl = md_match.group(1).strip()
            raw_url = md_match.group(2).strip()
            if raw_lbl.startswith("http"):
                raw_lbl = self._derive_readable_link_title(raw_url, fallback_context)
            label = html.escape(raw_lbl)
            url = self._sanitize_url(raw_url)
            return f'<a href="{url}" target="_blank" class="fm-pill" style="{pill_style}">{label} &rarr;</a>'

        url_match = re.search(r"(https?://[^\s<>\"'\)]+)", text)
        if url_match:
            url_raw = url_match.group(1).rstrip(".,;:")
            url = self._sanitize_url(url_raw)
            prefix = text[:url_match.start()].strip(" -:|")
            readable = prefix if prefix and not prefix.startswith("http") else self._derive_readable_link_title(url_raw, fallback_context)
            return f'<a href="{url}" target="_blank" class="fm-pill" style="{pill_style}">{html.escape(readable)} &rarr;</a>'

        return f'<span class="fm-muted" style="color: #52525B; font-size: 12px;">{html.escape(text)}</span>'

    def _format_seniority_html(self, seniority: Any) -> str:
        """Render Experience & Seniority alignment block matching Frontend Zinc UI (zero emojis)."""
        if not seniority or not isinstance(seniority, dict):
            return ""
        your_lvl = html.escape(str(seniority.get("your_level") or seniority.get("yourLevel") or "Mid"))
        req_lvl = html.escape(str(seniority.get("required_level") or seniority.get("requiredLevel") or "Target"))
        cand_yrs = seniority.get("years_experience") if seniority.get("years_experience") is not None else seniority.get("your_years")
        req_yrs = seniority.get("required_years") if seniority.get("required_years") is not None else seniority.get("requiredYears")
        summary_txt = seniority.get("summary") or seniority.get("alignment_summary") or seniority.get("seniority_reason") or ""
        rec_txt = seniority.get("recommendation") or seniority.get("advice") or ""

        raw_badge = str(seniority.get("alignment_badge") or seniority.get("seniority_status") or "").strip()
        # Strip leading/embedded emojis (e.g., '🟡 MINOR GAP' -> 'MINOR GAP')
        clean_badge = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]+", "", raw_badge).strip().upper()
        badge = html.escape(clean_badge)

        status_key = str(seniority.get("alignment_status") or "").lower()
        if "match" in status_key or clean_badge == "MATCH":
            b_bg, b_border, b_fg = "#ECFDF5", "#A7F3D0", "#047857"
        elif "significant" in status_key or "mismatch" in clean_badge or "gap" in clean_badge and "minor" not in clean_badge:
            b_bg, b_border, b_fg = "#FEF2F2", "#FECACA", "#B91C1C"
        else:
            b_bg, b_border, b_fg = "#FFFBEB", "#FDE68A", "#B45309"

        if cand_yrs is not None and req_yrs is not None:
            years_line = (
                f'Candidate: <strong class="fm-text" style="color: #18181B;">{cand_yrs} yrs ({your_lvl})</strong>'
                f' &nbsp;&bull;&nbsp; Role Requires: <strong class="fm-text" style="color: #18181B;">{req_yrs} yrs ({req_lvl})</strong>'
            )
        else:
            years_line = (
                f'Candidate Tier: <strong class="fm-text" style="color: #18181B;">{your_lvl}</strong>'
                f' &nbsp;&bull;&nbsp; Target Tier: <strong class="fm-text" style="color: #18181B;">{req_lvl}</strong>'
            )

        badge_html = (
            f'<span style="display: inline-block; padding: 3px 10px; background-color: {b_bg}; border: 1px solid {b_border}; color: {b_fg}; border-radius: 12px; font-size: 11px; font-weight: 700; white-space: nowrap;">{badge}</span>'
            if badge else ""
        )
        rec_html = (
            f'<div class="fm-divider" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #E4E4E7; font-size: 13px; color: #27272A;"><span class="fm-body">{_cid_icon("icon-info", 14)} <strong class="fm-text" style="color: #18181B;">Recommendation:</strong> {html.escape(str(rec_txt))}</span></div>'
            if rec_txt else ""
        )

        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 10px; margin-bottom: 20px;">
            <tr>
                <td style="padding: 18px 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 10px;">
                        <tr>
                            <td align="left" class="fm-text" style="font-size: 14px; font-weight: 700; color: #18181B;">
                                {_cid_icon("icon-trending", 16)} &nbsp;Experience &amp; Seniority Calibration
                            </td>
                            <td align="right">{badge_html}</td>
                        </tr>
                    </table>
                    <div class="fm-body" style="font-size: 13px; color: #3F3F46; margin-bottom: 6px;">{years_line}</div>
                    {f'<div class="fm-muted" style="font-size: 13px; color: #52525B; line-height: 1.55;">{html.escape(str(summary_txt))}</div>' if summary_txt else ""}
                    {rec_html}
                </td>
            </tr>
        </table>
        """

    def _format_friction_html(self, friction_points: Any) -> str:
        """Render identified Friction Points cards matching Frontend Zinc cards & CID severity icons."""
        if not friction_points or not isinstance(friction_points, list):
            return ""
        items_html = ""
        for fp in friction_points[:5]:
            if not isinstance(fp, dict):
                continue
            category = html.escape(str(fp.get("category") or "Gap").replace("_", " ").title())
            severity = str(fp.get("severity") or "medium").lower()
            if severity in ("high", "critical"):
                sev_color, sev_icon = "#EF4444", "icon-alert-circle"
            elif severity in ("medium", "warning"):
                sev_color, sev_icon = "#F59E0B", "icon-alert-triangle"
            else:
                sev_color, sev_icon = "#3B82F6", "icon-info"

            desc = html.escape(str(fp.get("description") or ""))
            sug = html.escape(str(fp.get("suggestion") or ""))
            items_html += f"""
            <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-left: 3px solid {sev_color}; border-radius: 8px; margin-bottom: 10px;">
                <tr>
                    <td style="padding: 13px 16px;">
                        <div style="font-size: 11px; font-weight: 700; color: {sev_color}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 5px;">
                            {_cid_icon(sev_icon, 13)} &nbsp;{category} &bull; {html.escape(severity.upper())}
                        </div>
                        {f'<div class="fm-body" style="font-size: 13px; color: #18181B; margin-bottom: 4px; line-height: 1.45;">{desc}</div>' if desc else ""}
                        {f'<div class="fm-muted" style="font-size: 12px; color: #52525B; line-height: 1.45;"><strong class="fm-text" style="color: #18181B;">Action:</strong> {sug}</div>' if sug else ""}
                    </td>
                </tr>
            </table>
            """
        if not items_html:
            return ""
        return f"""
        <div style="margin-bottom: 22px;">
            <div class="fm-text" style="font-size: 15px; font-weight: 700; color: #18181B; margin-bottom: 10px;">
                {_cid_icon("icon-alert-triangle", 15)} &nbsp;Key Friction Points &amp; Risk Mitigation
            </div>
            {items_html}
        </div>
        """

    def _format_ats_html(self, ats_opt: Any) -> str:
        """Render ATS Optimization Playbook matching Frontend Neutral Zinc design."""
        if not ats_opt or not isinstance(ats_opt, dict):
            return ""
        keywords = ats_opt.get("keywords") or []
        phrasing = ats_opt.get("phrasing") or []
        tips = ats_opt.get("formatting_tips") or []

        if not (keywords or phrasing or tips):
            return ""

        kw_html = ""
        if keywords:
            pills = "".join(
                f'<span class="fm-pill" style="display: inline-block; margin: 3px 6px 3px 0; padding: 4px 11px; background-color: #FFFFFF; border: 1px solid #D4D4D8; color: #18181B; border-radius: 14px; font-size: 12px; font-weight: 600;">{html.escape(str(k))}</span>'
                for k in keywords[:8]
            )
            kw_html = f'<div style="margin-bottom: 16px;"><div class="fm-muted" style="font-size: 11px; font-weight: 700; color: #71717A; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.6px;">High-Impact Keywords to Include</div><div>{pills}</div></div>'

        phrasing_html = ""
        if phrasing:
            rows = ""
            for p in phrasing[:3]:
                if not isinstance(p, dict):
                    continue
                orig = html.escape(str(p.get("original") or ""))
                sugg = html.escape(str(p.get("suggested") or ""))
                if orig or sugg:
                    rows += f"""
                    <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" class="fm-card" style="background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; margin-bottom: 8px;">
                        <tr>
                            <td style="padding: 12px 14px; font-size: 12px; line-height: 1.5;">
                                {f'<div class="fm-muted" style="color: #DC2626; margin-bottom: 5px;"><strong>Before:</strong> {orig}</div>' if orig else ""}
                                {f'<div class="fm-body" style="color: #059669;"><strong>Suggested:</strong> {sugg}</div>' if sugg else ""}
                            </td>
                        </tr>
                    </table>
                    """
            if rows:
                phrasing_html = f'<div style="margin-bottom: 16px;"><div class="fm-muted" style="font-size: 11px; font-weight: 700; color: #71717A; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.6px;">Resume Bullet Upgrades</div>{rows}</div>'

        tips_html = ""
        if tips:
            tip_items = "".join(f'<li class="fm-body" style="margin-bottom: 5px; color: #3F3F46;">{html.escape(str(t))}</li>' for t in tips[:4])
            tips_html = f'<div><div class="fm-muted" style="font-size: 11px; font-weight: 700; color: #71717A; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.6px;">ATS Formatting Tips</div><ul style="margin: 0; padding-left: 18px; font-size: 12px; line-height: 1.5;">{tip_items}</ul></div>'

        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 10px; margin-bottom: 22px;">
            <tr>
                <td style="padding: 18px 20px;">
                    <div class="fm-text" style="font-size: 15px; font-weight: 700; color: #18181B; margin-bottom: 14px;">
                        {_cid_icon("icon-target", 16)} &nbsp;ATS Resume Optimization Playbook
                    </div>
                    {kw_html}
                    {phrasing_html}
                    {tips_html}
                </td>
            </tr>
        </table>
        """

    def _wrap_zinc_email_shell(
        self,
        candidate_name: str,
        target_role: str,
        body_html: str,
        matched_from_sharepoint: bool = False,
        sharepoint_source_file: Optional[str] = None,
    ) -> str:
        """Wrap inner report sections in the Frontend-aligned Neutral Zinc Light-First email container."""
        sp_badge = (
            f'''<div class="fm-surface fm-body" style="display: inline-block; margin-top: 12px; padding: 6px 12px; background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 8px; font-size: 12px; font-weight: 600; color: #3F3F46;">
                {_cid_icon("icon-file", 14)} &nbsp;Evaluated against official opening: <strong class="fm-text" style="color: #18181B;">{html.escape(target_role)}</strong> ({html.escape(sharepoint_source_file or "SharePoint")})
            </div>'''
            if matched_from_sharepoint else ""
        )
        return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <title>Candidate Talent Intelligence Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ color-scheme: light dark; supported-color-schemes: light dark; }}
        body {{ margin: 0; padding: 0; background-color: #F4F4F5; color: #18181B; }}
        @media (prefers-color-scheme: dark) {{
            .fm-bg {{ background-color: #09090B !important; }}
            .fm-card {{ background-color: #18181B !important; border-color: #27272A !important; }}
            .fm-head {{ background-color: #18181B !important; border-color: #27272A !important; }}
            .fm-surface {{ background-color: #111113 !important; border-color: #27272A !important; }}
            .fm-track {{ background-color: #27272A !important; }}
            .fm-divider {{ border-color: #27272A !important; }}
            .fm-text {{ color: #FAFAFA !important; }}
            .fm-body {{ color: #E4E4E7 !important; }}
            .fm-muted {{ color: #A1A1AA !important; }}
            .fm-pill {{ background-color: #27272A !important; border-color: #3F3F46 !important; color: #FAFAFA !important; }}
        }}
        [data-ogsb] .fm-bg {{ background-color: #09090B !important; }}
        [data-ogsb] .fm-card {{ background-color: #18181B !important; border-color: #27272A !important; }}
        [data-ogsb] .fm-head {{ background-color: #18181B !important; border-color: #27272A !important; }}
        [data-ogsb] .fm-surface {{ background-color: #111113 !important; border-color: #27272A !important; }}
        [data-ogsb] .fm-track {{ background-color: #27272A !important; }}
        [data-ogsb] .fm-pill {{ background-color: #27272A !important; border-color: #3F3F46 !important; }}
        [data-ogsc] .fm-text {{ color: #FAFAFA !important; }}
        [data-ogsc] .fm-body {{ color: #E4E4E7 !important; }}
        [data-ogsc] .fm-muted {{ color: #A1A1AA !important; }}
        [data-ogsc] .fm-pill {{ color: #FAFAFA !important; }}
    </style>
</head>
<body bgcolor="#F4F4F5" class="fm-bg" style="margin: 0; padding: 0; background-color: #F4F4F5; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #18181B;">
    <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#F4F4F5" class="fm-bg" style="background-color: #F4F4F5; padding: 28px 14px;">
        <tr>
            <td align="center">
                <table width="680" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" class="fm-card" style="max-width: 680px; width: 100%; background-color: #FFFFFF; border-radius: 14px; overflow: hidden; border: 1px solid #E4E4E7;">
                    <tr>
                        <td bgcolor="#FFFFFF" class="fm-head" style="background-color: #FFFFFF; padding: 30px 34px 26px 34px; text-align: left; border-bottom: 1px solid #E4E4E7;">
                            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #6366F1; font-weight: 700; margin-bottom: 8px;">
                                Friction Matcher &bull; Autonomous HR Talent Intelligence
                            </div>
                            <h1 class="fm-text" style="color: #18181B; font-size: 24px; font-weight: 800; margin: 0 0 8px 0; letter-spacing: -0.4px;">
                                Talent Evaluation &amp; Career Roadmap
                            </h1>
                            <p class="fm-muted" style="color: #52525B; font-size: 14px; margin: 0;">
                                Candidate: <strong class="fm-text" style="color: #18181B;">{html.escape(candidate_name)}</strong> &nbsp;&bull;&nbsp; Target: <strong class="fm-text" style="color: #18181B;">{html.escape(target_role)}</strong>
                            </p>
                            {sp_badge}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 28px 34px;">
                            {body_html}
                        </td>
                    </tr>
                    <tr>
                        <td bgcolor="#FAFAFA" class="fm-surface fm-divider" style="background-color: #FAFAFA; border-top: 1px solid #E4E4E7; padding: 22px 34px; text-align: center;">
                            <div class="fm-text" style="font-size: 13px; font-weight: 700; color: #18181B; margin-bottom: 4px;">
                                Friction Matcher AI Talent Suite
                            </div>
                            <div class="fm-muted" style="font-size: 12px; color: #71717A; margin-bottom: 8px; line-height: 1.5;">
                                This evaluation was processed autonomously by the Friction HR Agent directly in-memory.<br/>
                                In adherence to strict privacy standards, your resume was streamed in RAM and never written to disk storage.
                            </div>
                            <div class="fm-muted" style="font-size: 11px; color: #A1A1AA;">
                                &copy; 2026 Friction Matcher &bull; Confidential &bull; Generated for candidate {html.escape(candidate_name)}
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    def generate_professional_html_report(
        self,
        candidate_name: str,
        target_role: str,
        analysis: Dict[str, Any],
        matched_from_sharepoint: bool = False,
        sharepoint_source_file: Optional[str] = None,
    ) -> str:
        """
        Render a Frontend-parity Neutral Zinc HTML email report (Light-first with clean Dark Mode
        overrides, zero linear-gradient saturation, Inter typography, and CID vector icons).
        """
        status_flag = str(analysis.get("status") or "").lower()

        # Dedicated Frontend-Parity Career Pivot / Domain Mismatch View (matches DomainMismatchCard.jsx)
        if status_flag == "domain_mismatch":
            res_dom = html.escape(str(analysis.get("resume_domain") or "Your Current Background"))
            jd_dom = html.escape(str(analysis.get("jd_domain") or target_role))
            mismatch_msg = html.escape(str(analysis.get("message") or f"Your background is in {res_dom}, whereas this opening requires {jd_dom}."))
            transition_roadmap_html = self._format_roadmap_html(analysis.get("roadmap")) if analysis.get("roadmap") else ""
            mismatch_body = f"""
            <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-left: 3px solid #F59E0B; border-radius: 12px; margin-bottom: 22px;">
                <tr>
                    <td style="padding: 20px 22px;">
                        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #D97706; margin-bottom: 8px;">
                            {_cid_icon("icon-alert-triangle", 14)} &nbsp;Cross-Domain Career Transition Detected
                        </div>
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 12px 0;">
                            <tr>
                                <td width="48%" bgcolor="#FFFFFF" class="fm-card" style="background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; padding: 12px 14px;">
                                    <div class="fm-muted" style="font-size: 11px; text-transform: uppercase; color: #71717A;">Your Background</div>
                                    <div class="fm-text" style="font-size: 14px; font-weight: 700; color: #18181B;">{res_dom}</div>
                                </td>
                                <td width="4%"></td>
                                <td width="48%" bgcolor="#FFFFFF" class="fm-card" style="background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 8px; padding: 12px 14px;">
                                    <div class="fm-muted" style="font-size: 11px; text-transform: uppercase; color: #71717A;">Target Role Domain</div>
                                    <div class="fm-text" style="font-size: 14px; font-weight: 700; color: #18181B;">{jd_dom}</div>
                                </td>
                            </tr>
                        </table>
                        <div class="fm-body" style="font-size: 14px; color: #27272A; line-height: 1.6; margin-top: 8px;">
                            {mismatch_msg}
                        </div>
                    </td>
                </tr>
            </table>
            {f'<div style="margin-bottom: 16px;"><div class="fm-text" style="font-size: 15px; font-weight: 700; color: #18181B; margin-bottom: 10px;">{_cid_icon("icon-calendar", 16)} &nbsp;Recommended Career Transition Roadmap</div>{transition_roadmap_html}</div>' if transition_roadmap_html else ""}
            """
            return self._wrap_zinc_email_shell(
                candidate_name=candidate_name,
                target_role=target_role,
                body_html=mismatch_body,
                matched_from_sharepoint=matched_from_sharepoint,
                sharepoint_source_file=sharepoint_source_file,
            )

        # Dedicated Frontend-Parity Unparseable JD Clarification View (matches UnparseableJdCard.jsx)
        if status_flag == "unparseable_jd" or analysis.get("overall_score") is None and analysis.get("overallScore") is None:
            clarify_msg = html.escape(str(analysis.get("message") or "Please reply mentioning the specific role or attach the job requirements so we can evaluate your profile accurately."))
            unparseable_body = f"""
            <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-left: 3px solid #3B82F6; border-radius: 12px; margin-bottom: 20px;">
                <tr>
                    <td style="padding: 20px 22px;">
                        <div class="fm-text" style="font-size: 15px; font-weight: 700; color: #18181B; margin-bottom: 8px;">
                            {_cid_icon("icon-info", 16)} &nbsp;Additional Role Details Needed for Scoring
                        </div>
                        <div class="fm-body" style="font-size: 14px; color: #27272A; line-height: 1.6; margin-bottom: 10px;">
                            {clarify_msg}
                        </div>
                        <div class="fm-muted" style="font-size: 13px; color: #52525B;">
                            Tip: Include the target job title in your email subject line (e.g., <em>Application for AI Engineer</em>) or paste the job requirements in your message body.
                        </div>
                    </td>
                </tr>
            </table>
            """
            return self._wrap_zinc_email_shell(
                candidate_name=candidate_name,
                target_role=target_role,
                body_html=unparseable_body,
                matched_from_sharepoint=matched_from_sharepoint,
                sharepoint_source_file=sharepoint_source_file,
            )

        overall_score = analysis.get("overall_score") if analysis.get("overall_score") is not None else (analysis.get("overallScore") or 0)
        executive_summary = analysis.get("executive_summary") or analysis.get("executiveSummary") or "Your profile was evaluated against the target role requirements."
        strengths = analysis.get("strengths") or []
        skill_gaps = analysis.get("skill_gaps") or analysis.get("skillGaps") or []
        roadmap = analysis.get("roadmap") or {}

        # Semantic score tokens aligned with Frontend ScoreCard
        if overall_score >= 75:
            score_color = "#10B981"  # Emerald-500
            score_bg = "#ECFDF5"
            score_label = "Strong Fit"
        elif overall_score >= 50:
            score_color = "#D97706"  # Amber-600
            score_bg = "#FFFBEB"
            score_label = "Competitive Match"
        else:
            score_color = "#EF4444"  # Red-500
            score_bg = "#FEF2F2"
            score_label = "Needs Targeted Upskilling"

        # Score Breakdown items (preserve valid 0 values safely)
        breakdown = analysis.get("score_breakdown") or analysis.get("scoreBreakdown") or {}
        if isinstance(breakdown, dict):
            skills_match = breakdown.get("skills_match") if breakdown.get("skills_match") is not None else (breakdown.get("skillsMatch") if breakdown.get("skillsMatch") is not None else overall_score)
            seniority_match = breakdown.get("seniority_match") if breakdown.get("seniority_match") is not None else (breakdown.get("seniorityMatch") if breakdown.get("seniorityMatch") is not None else overall_score)
            domain_match = breakdown.get("domain_match") if breakdown.get("domain_match") is not None else (breakdown.get("domainMatch") if breakdown.get("domainMatch") is not None else overall_score)
        else:
            skills_match = getattr(breakdown, "skills_match", overall_score)
            seniority_match = getattr(breakdown, "seniority_match", overall_score)
            domain_match = getattr(breakdown, "domain_match", overall_score)

        # Format Strengths List HTML (CID CheckCircle icon, zero emoji/Unicode)
        strengths_html = ""
        for s in strengths[:6]:
            strengths_html += f"""
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td width="20" valign="top" style="padding-top: 2px;">{_cid_icon("icon-check", 14)}</td>
                    <td class="fm-body" style="font-size: 13px; color: #27272A; line-height: 1.45;">{html.escape(str(s))}</td>
                </tr>
            </table>
            """
        if not strengths_html:
            strengths_html = '<div class="fm-muted" style="font-size: 13px; color: #71717A;">Strong foundational domain competencies identified.</div>'

        # Format Skill Gaps List HTML (CID AlertTriangle icon, zero emoji/Unicode)
        gaps_html = ""
        for g in skill_gaps[:6]:
            gaps_html += f"""
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td width="20" valign="top" style="padding-top: 2px;">{_cid_icon("icon-alert-triangle", 14)}</td>
                    <td class="fm-body" style="font-size: 13px; color: #27272A; line-height: 1.45;">{html.escape(str(g))}</td>
                </tr>
            </table>
            """
        if not gaps_html:
            gaps_html = '<div class="fm-muted" style="font-size: 13px; color: #71717A;">No critical skill gaps detected for this role.</div>'

        # Additional rich sections matching frontend
        seniority_html = self._format_seniority_html(analysis.get("seniority_analysis") or analysis.get("seniorityAnalysis"))
        friction_html = self._format_friction_html(analysis.get("friction_points") or analysis.get("frictionPoints"))
        ats_html = self._format_ats_html(analysis.get("ats_optimization") or analysis.get("atsOptimization"))

        # Extract and format Verified Resources with clean titles & non-wrapping Open button
        verified_resources = self._extract_resources_from_roadmap(roadmap)
        resources_html = ""
        for res in verified_resources[:8]:
            title = html.escape(res.get("title", "Upskilling Course / Documentation"))
            url = self._sanitize_url(res.get("url", "#"))
            platform = html.escape(res.get("platform", "Verified Resource"))
            meta_tag = ""
            if res.get("skill"):
                meta_tag = f'<div class="fm-muted" style="font-size: 11px; color: #71717A; margin-top: 2px;">Skill: {html.escape(str(res["skill"]))}</div>'
            action_cell = (
                f'<a href="{url}" target="_blank" class="fm-pill" style="display: inline-block; padding: 5px 11px; background-color: #FFFFFF; border: 1px solid #D4D4D8; color: #18181B; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600; white-space: nowrap;">Open &rarr;</a>'
                if url != "#" else '<span class="fm-muted" style="color: #71717A; font-size: 12px;">Reference</span>'
            )
            resources_html += f"""
            <tr class="fm-divider" style="border-bottom: 1px solid #E4E4E7;">
                <td width="56%" class="fm-text" style="padding: 12px 14px; font-weight: 600; color: #18181B; font-size: 13px; word-break: break-word;">{title}{meta_tag}</td>
                <td width="22%" class="fm-muted" style="padding: 12px 10px; color: #52525B; font-size: 12px;">{platform}</td>
                <td width="22%" style="padding: 12px 14px 12px 8px; text-align: right; white-space: nowrap;">{action_cell}</td>
            </tr>
            """
        if not resources_html:
            resources_html = """
            <tr>
                <td colspan="3" class="fm-muted" style="padding: 16px; color: #71717A; text-align: center; font-size: 13px;">
                    Consult the personalized roadmap below for recommended technical reference modules.
                </td>
            </tr>
            """

        # Format detailed weekly/daily Roadmap with clickable links
        roadmap_summary_html = self._format_roadmap_html(roadmap)
        roadmap_heading = html.escape(str(roadmap.get("title"))) if isinstance(roadmap, dict) and roadmap.get("title") else "Personalized Transition &amp; Upskilling Roadmap"

        # Helper to render an Outlook-safe metric progress bar row (pure HTML tables)
        def _metric_row(label_text: str, pct: Any, bar_color: str) -> str:
            return f"""
            <div style="margin-bottom: 12px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 5px;">
                    <tr>
                        <td align="left" class="fm-body" style="font-size: 13px; font-weight: 500; color: #3F3F46;">{label_text}</td>
                        <td align="right" class="fm-text" style="font-size: 13px; font-weight: 700; color: #18181B; white-space: nowrap; padding-left: 8px;">{pct}%</td>
                    </tr>
                </table>
                <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#E4E4E7" class="fm-track" style="background-color: #E4E4E7; border-radius: 4px; height: 7px;">
                    <tr>
                        <td width="{pct}%" bgcolor="{bar_color}" style="background-color: {bar_color}; height: 7px; border-radius: 4px; font-size: 1px; line-height: 1px;">&nbsp;</td>
                        <td style="font-size: 1px; line-height: 1px;">&nbsp;</td>
                    </tr>
                </table>
            </div>
            """

        # Build main inner body HTML and wrap in shared Neutral Zinc Light-First email container
        body_html = f"""
            <!-- Overall Score Card -->
            <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border-radius: 12px; border: 1px solid #E4E4E7; margin-bottom: 22px;">
                <tr>
                    <td valign="middle" class="fm-divider" style="padding: 24px 20px; text-align: center; border-right: 1px solid #E4E4E7;" width="36%">
                        <div class="fm-muted" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #71717A; font-weight: 700; margin-bottom: 6px;">Overall Fit Score</div>
                        <div style="font-size: 46px; font-weight: 800; color: {score_color}; line-height: 1;">{overall_score}%</div>
                        <div style="display: inline-block; margin-top: 10px; padding: 4px 12px; background-color: {score_bg}; border: 1px solid {score_color}; border-radius: 14px; font-size: 12px; font-weight: 700; color: {score_color}; white-space: nowrap;">
                            {score_label}
                        </div>
                    </td>
                    <td valign="middle" style="padding: 20px 24px;" width="64%">
                        <div class="fm-muted" style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #71717A; font-weight: 700; margin-bottom: 14px;">Component Alignment</div>
                        {_metric_row("Technical Skills Match", skills_match, "#6366F1")}
                        {_metric_row("Experience &amp; Seniority", seniority_match, "#06B6D4")}
                        {_metric_row("Domain Match", domain_match, "#10B981")}
                    </td>
                </tr>
            </table>

            <!-- Executive Summary / Recruiter's Verdict -->
            <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 12px; margin-bottom: 22px;">
                <tr>
                    <td style="padding: 18px 20px;">
                        <div class="fm-text" style="font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #18181B; margin-bottom: 8px;">
                            {_cid_icon("icon-user-check", 16)} &nbsp;Recruiter&apos;s Executive Verdict
                        </div>
                        <div class="fm-body" style="font-size: 14px; color: #27272A; line-height: 1.6;">
                            {html.escape(executive_summary)}
                        </div>
                    </td>
                </tr>
            </table>

            <!-- Strengths & Gaps (2-Column Grid matching Frontend Lists.jsx) -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 22px;">
                <tr>
                    <td width="48%" valign="top" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 10px; padding: 18px 20px;">
                        <div class="fm-text fm-divider" style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #18181B; border-bottom: 1px solid #E4E4E7; padding-bottom: 8px; margin-bottom: 12px;">
                            {_cid_icon("icon-check", 14)} &nbsp;Key Strengths &amp; Proficiencies
                        </div>
                        {strengths_html}
                    </td>
                    <td width="4%"></td>
                    <td width="48%" valign="top" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 10px; padding: 18px 20px;">
                        <div class="fm-text fm-divider" style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #18181B; border-bottom: 1px solid #E4E4E7; padding-bottom: 8px; margin-bottom: 12px;">
                            {_cid_icon("icon-alert-triangle", 14)} &nbsp;Priority Development Gaps
                        </div>
                        {gaps_html}
                    </td>
                </tr>
            </table>

            <!-- Seniority Calibration -->
            {seniority_html}

            <!-- Key Friction Points -->
            {friction_html}

            <!-- ATS Optimization Playbook -->
            {ats_html}

            <!-- Verified Learning Resources -->
            <div style="margin-bottom: 24px;">
                <div class="fm-text" style="font-size: 15px; font-weight: 700; color: #18181B; margin-bottom: 10px;">
                    {_cid_icon("icon-book", 16)} &nbsp;Verified Learning Resources &amp; Certifications
                </div>
                <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="width: 100%; table-layout: fixed; background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 10px; overflow: hidden; border-collapse: collapse;">
                    <thead bgcolor="#F4F4F5" class="fm-track" style="background-color: #F4F4F5; color: #71717A; font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px;">
                        <tr class="fm-divider" style="border-bottom: 1px solid #E4E4E7;">
                            <th width="56%" class="fm-muted" style="padding: 11px 14px; text-align: left;">Resource / Guide</th>
                            <th width="22%" class="fm-muted" style="padding: 11px 10px; text-align: left;">Platform</th>
                            <th width="22%" class="fm-muted" style="padding: 11px 14px 11px 8px; text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {resources_html}
                    </tbody>
                </table>
            </div>

            <!-- Personalized Weekly Roadmap -->
            <div style="margin-bottom: 16px;">
                <div class="fm-text" style="font-size: 15px; font-weight: 700; color: #18181B; margin-bottom: 10px;">
                    {_cid_icon("icon-calendar", 16)} &nbsp;{roadmap_heading}
                </div>
                {roadmap_summary_html}
            </div>
        """
        return self._wrap_zinc_email_shell(
            candidate_name=candidate_name,
            target_role=target_role,
            body_html=body_html,
            matched_from_sharepoint=matched_from_sharepoint,
            sharepoint_source_file=sharepoint_source_file,
        )

    def _extract_resources_from_roadmap(self, roadmap: Any) -> List[Dict[str, str]]:
        """Extract verified RAG resources and inline roadmap links with human-readable titles (deduplicated by URL)."""
        resources: List[Dict[str, str]] = []
        seen_urls = set()

        def _add_resource(title: str, url: str, platform: str, skill: str = ""):
            norm_url = (url or "#").strip()
            if norm_url != "#" and norm_url in seen_urls:
                return
            if norm_url != "#":
                seen_urls.add(norm_url)
            final_title = (title or "").strip()
            if not final_title or final_title.startswith("http"):
                final_title = self._derive_readable_link_title(norm_url)
            final_platform = (platform or "").strip() or self._derive_platform_from_url(norm_url)
            resources.append({
                "title": final_title,
                "url": norm_url,
                "platform": final_platform,
                "skill": skill.strip() if skill else "",
            })

        def _parse_entry(r: Any, day_context: str = ""):
            if isinstance(r, dict):
                raw_url = r.get("url") or r.get("link") or "#"
                raw_title = r.get("title") or r.get("name") or ""
                if not raw_title or str(raw_title).startswith("http"):
                    raw_title = self._derive_readable_link_title(str(raw_url), day_context)
                skill_tag = r.get("skill") or ""
                if not skill_tag and isinstance(r.get("skills"), list):
                    skill_tag = ", ".join(str(s) for s in r["skills"][:2])
                _add_resource(
                    title=str(raw_title),
                    url=str(raw_url),
                    platform=r.get("platform") or r.get("source") or self._derive_platform_from_url(str(raw_url)),
                    skill=skill_tag,
                )
            elif isinstance(r, str):
                text = r.strip()
                md_match = re.search(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", text)
                if md_match:
                    lbl = md_match.group(1).strip()
                    u = md_match.group(2).strip()
                    if lbl.startswith("http"):
                        lbl = self._derive_readable_link_title(u, day_context)
                    _add_resource(lbl, u, self._derive_platform_from_url(u))
                    return
                url_match = re.search(r"(https?://[^\s<>\"'\)]+)", text)
                if url_match:
                    raw_url = url_match.group(1).rstrip(".,;:")
                    prefix = text[:url_match.start()].strip(" -:|")
                    label = prefix if prefix and not prefix.startswith("http") else self._derive_readable_link_title(raw_url, day_context)
                    _add_resource(label, raw_url, self._derive_platform_from_url(raw_url))

        if not isinstance(roadmap, dict):
            return resources

        # 1. Primary RAG verified resources list attached by Phase3Explainer
        for key in ("verified_resources", "resources"):
            if isinstance(roadmap.get(key), list):
                for item in roadmap[key]:
                    _parse_entry(item)

        # 2. Weekly -> Daily roadmap resources (markdown links & URLs)
        weeks = roadmap.get("weeks") or []
        if isinstance(weeks, list):
            for week in weeks:
                if not isinstance(week, dict):
                    continue
                for day in week.get("days") or []:
                    if isinstance(day, dict) and isinstance(day.get("resources"), list):
                        day_ctx = str(day.get("action") or week.get("focus") or "").strip()
                        for item in day["resources"]:
                            _parse_entry(item, day_context=day_ctx)

        # 3. Legacy milestones / phases fallback
        milestones = roadmap.get("milestones") or roadmap.get("phases") or []
        if isinstance(milestones, list):
            for m in milestones:
                if isinstance(m, dict) and isinstance(m.get("resources"), list):
                    for item in m["resources"]:
                        _parse_entry(item)

        return resources

    def _format_roadmap_html(self, roadmap: Any) -> str:
        """Render the week-by-week/day-by-day roadmap matching Frontend Neutral Zinc layout & CID links."""
        if not roadmap or not isinstance(roadmap, dict):
            return """
            <div class="fm-surface fm-muted" style="background-color: #FAFAFA; border: 1px dashed #D4D4D8; border-radius: 8px; padding: 14px 18px; font-size: 13px; color: #71717A;">
                Roadmap milestones are tailored to candidates seeking domain transitions. Your profile meets standard qualification criteria.
            </div>
            """

        weeks = roadmap.get("weeks") or []
        if isinstance(weeks, list) and len(weeks) > 0:
            week_colors = ["#6366F1", "#06B6D4", "#10B981", "#8B5CF6", "#F59E0B"]
            html_out = ""
            for idx, week in enumerate(weeks[:6]):
                if not isinstance(week, dict):
                    continue
                wk_num = week.get("week") or (idx + 1)
                focus = html.escape(str(week.get("focus") or "Targeted Skill Development"))
                dot_color = week_colors[idx % len(week_colors)]
                days_html = ""
                for day in (week.get("days") or [])[:5]:
                    if not isinstance(day, dict):
                        continue
                    day_num = day.get("day") or ""
                    action_raw = str(day.get("action") or "Complete guided module")
                    action = html.escape(action_raw)
                    est_time = html.escape(str(day.get("estimated_time") or ""))
                    res_links = [
                        self._linkify_resource_html(r, fallback_context=action_raw)
                        for r in (day.get("resources") or [])
                        if r
                    ]
                    res_line = (
                        f'<div style="margin-top: 6px;">{" ".join(res_links)}</div>'
                        if res_links else ""
                    )
                    time_badge = (
                        f'<span class="fm-pill" style="display: inline-block; margin-left: 6px; padding: 1px 7px; background-color: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 10px; color: #71717A; font-size: 11px;">{est_time}</span>'
                        if est_time else ""
                    )
                    days_html += f"""
                    <div class="fm-divider" style="padding: 10px 0; border-top: 1px solid #E4E4E7;">
                        <div class="fm-body" style="font-size: 13px; color: #27272A; line-height: 1.45;">
                            <strong class="fm-text" style="color: #18181B;">Day {html.escape(str(day_num))}:</strong> {action}{time_badge}
                        </div>
                        {res_line}
                    </div>
                    """

                html_out += f"""
                <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-left: 3px solid {dot_color}; border-radius: 10px; margin-bottom: 12px;">
                    <tr>
                        <td style="padding: 16px 18px;">
                            <div class="fm-text" style="font-size: 14px; font-weight: 700; color: #18181B; margin-bottom: 8px;">
                                Week {html.escape(str(wk_num))}: {focus}
                            </div>
                            {days_html}
                        </td>
                    </tr>
                </table>
                """

            # Architecture diagrams if provided by RAG
            diagrams = roadmap.get("architecture_diagrams") or []
            if isinstance(diagrams, list) and diagrams:
                diag_items = ""
                for d in diagrams[:2]:
                    if isinstance(d, dict):
                        d_title = html.escape(str(d.get("title") or "Architecture Reference"))
                        d_desc = html.escape(str(d.get("description") or ""))
                        d_url = self._sanitize_url(d.get("url") or d.get("image_url") or "")
                        link_tag = f' &mdash; <a href="{d_url}" target="_blank" style="color: #6366F1; font-weight: 600;">View Diagram &rarr;</a>' if d_url != "#" else ""
                        diag_items += f'<li class="fm-body" style="margin-bottom: 5px; color: #3F3F46;"><strong class="fm-text" style="color: #18181B;">{d_title}</strong>{f": {d_desc}" if d_desc else ""}{link_tag}</li>'
                if diag_items:
                    html_out += f"""
                    <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 10px; margin-top: 8px;">
                        <tr>
                            <td style="padding: 14px 18px;">
                                <div class="fm-muted" style="font-size: 11px; font-weight: 700; color: #71717A; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 6px;">Recommended System Architecture Blueprints</div>
                                <ul style="margin: 0; padding-left: 18px; font-size: 12px;">{diag_items}</ul>
                            </td>
                        </tr>
                    </table>
                    """

            if html_out:
                return html_out

        # Fallback to 30/60/90-day structural cards if LLM weeks array wasn't populated
        phases = [
            ("Days 1 - 30: Foundational Mastery", "#6366F1", "Close critical skill gaps, study industry standards, and complete foundational certifications."),
            ("Days 31 - 60: Applied Projects & Practical Execution", "#06B6D4", "Build real-world production prototypes and implement portfolio-grade solutions."),
            ("Days 61 - 90: Interview Readiness & Production Hardening", "#10B981", "Master technical domain interviews, architectural scenarios, and final recruiter screenings."),
        ]

        html_out = ""
        for title, dot_color, default_desc in phases:
            html_out += f"""
            <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#FAFAFA" class="fm-surface" style="background-color: #FAFAFA; border: 1px solid #E4E4E7; border-left: 3px solid {dot_color}; border-radius: 8px; margin-bottom: 10px;">
                <tr>
                    <td style="padding: 14px 18px;">
                        <div class="fm-text" style="margin-bottom: 4px;">
                            <span style="display: inline-block; width: 8px; height: 8px; background-color: {dot_color}; border-radius: 50%; margin-right: 8px;"></span>
                            <strong style="font-size: 13px;">{title}</strong>
                        </div>
                        <div class="fm-muted" style="font-size: 12px; color: #52525B; padding-left: 16px; line-height: 1.45;">
                            {default_desc}
                        </div>
                    </td>
                </tr>
            </table>
            """

        return html_out

    async def process_candidate_message(
        self,
        message: Dict[str, Any],
        orchestrator: Any,
    ) -> Dict[str, Any]:
        """
        Process a single candidate email:
        1. Parse sender metadata.
        2. Stream attachments in-memory to extract resume text.
        3. Infer target role.
        4. Execute full Friction AI analysis via DeterministicOrchestrator.
        5. Dispatch professional HTML response email to candidate.
        6. Mark message as read (idempotency).
        """
        message_id = message.get("id")
        subject = message.get("subject", "Job Application")
        sender_info = message.get("from", {}).get("emailAddress", {})
        sender_email = (sender_info.get("address") or "").strip()
        sender_name = sender_info.get("name") or sender_email.split("@")[0] if sender_email else "Candidate"

        # Filter automated system notices, bounce-backs, and our own outbound evaluation replies (prevents self-reply loops)
        system_senders = ["noreply", "no-reply", "mailer-daemon", "postmaster", "microsoft.com", "notifications"]
        is_system_sender = any(k in sender_email.lower() for k in system_senders)
        subj_lower = subject.lower().strip()
        body_preview_lower = str(message.get("bodyPreview") or "").lower()
        body_content_lower = str(message.get("body", {}).get("content") or "").lower()
        is_bounce_back = any(
            subj_lower.startswith(b) for b in [
                "undeliverable:", "delivery status notification", "failed:", "failure notice", "returned mail"
            ]
        )
        is_self_reply = (
            subj_lower.startswith("your talent evaluation & roadmap:")
            or "resume attachment required" in subj_lower
            or "friction matcher ai talent suite" in body_preview_lower
            or "friction matcher ai talent suite" in body_content_lower
        )
        if is_system_sender or is_bounce_back or is_self_reply:
            reason = "self_evaluation_reply" if is_self_reply else "automated_system_email"
            logger.info(f"Skipping message ({reason}) from {sender_email} (Subject: '{subject}')")
            if settings.outlook_mark_as_read:
                await self.mark_message_as_read(message_id)
            return {
                "messageId": message_id,
                "status": "ignored_system_email",
                "reason": reason,
                "sender": sender_email,
            }

        logger.info(f"Processing candidate email from: {_mask_email(sender_email)} | Subject: {subject}")

        # Fetch attachments
        attachments = []
        if message.get("hasAttachments", False):
            attachments = await self.fetch_attachments(message_id)

        # Extract resume text in-memory (non-blocking worker thread)
        resume_text, source_name = await self.extract_resume_text_in_memory_async(message, attachments)
        if not resume_text:
            has_ref_att = any(
                "referenceAttachment" in str(a.get("@odata.type") or "")
                for a in attachments
            )
            logger.warning(
                f"No parseable resume found in email from {_mask_email(sender_email)}"
                f"{' (cloud reference link detected)' if has_ref_att else ''}."
            )
            clarification_sent = True
            if settings.outlook_auto_reply_enabled and sender_email:
                ref_note = (
                    "<p>We noticed a cloud/OneDrive link was attached instead of a direct file. "
                    "Our automated system requires a direct file attachment for in-memory evaluation.</p>"
                    if has_ref_att else ""
                )
                clarification_sent = await self.send_reply_email(
                    to_address=sender_email,
                    subject=f"Re: {subject} - Resume Attachment Required",
                    html_body=(
                        f"<p>Dear {html.escape(sender_name)},</p>"
                        f"{ref_note}"
                        f"<p>Thank you for reaching out regarding career opportunities. We were unable to read a resume "
                        f"from your email. Please reply attaching your resume as a <strong>PDF</strong> or <strong>Word (.docx)</strong> "
                        f"document so our autonomous talent agent can evaluate your profile.</p>"
                        f"<p>Best regards,<br/>Friction Talent Intelligence Team</p>"
                    ),
                )
            if settings.outlook_mark_as_read and clarification_sent:
                await self.mark_message_as_read(message_id)

            return {
                "messageId": message_id,
                "status": "missing_resume",
                "sender": sender_email,
                "source": "none",
            }

        # Extract candidate real name from resume text or filename
        candidate_name = self.extract_candidate_name(
            resume_text=resume_text,
            attachment_name=source_name,
            fallback_sender=sender_name,
        )

        # Determine target JD: Check SharePoint active JDs first, fallback to subject role inference
        target_role = re.sub(r"^(?:\s*(?:re|fwd|fw)\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()
        matched_from_sharepoint = False
        sharepoint_source_file = None

        try:
            from app.services.sharepoint_service import sharepoint_service
            if sharepoint_service.is_configured():
                sp_match = await sharepoint_service.find_best_matching_jd(
                    candidate_resume_text=resume_text,
                    preferred_role=target_role if target_role and len(target_role) > 3 else None,
                )
                if sp_match.get("found"):
                    target_jd = sp_match["jd_text"]
                    target_role = sp_match["job_title"]
                    matched_from_sharepoint = True
                    sharepoint_source_file = sp_match.get("source_file")
                    logger.info(
                        f"Matched candidate against official SharePoint JD: '{target_role}' "
                        f"({sharepoint_source_file}) [mode: {sp_match.get('selection_mode')}]"
                    )
                else:
                    target_jd = self.infer_target_role_and_jd(subject, resume_text)
            else:
                target_jd = self.infer_target_role_and_jd(subject, resume_text)
        except Exception as e:
            logger.warning(f"SharePoint matching fallback to role inference: {e}")
            target_jd = self.infer_target_role_and_jd(subject, resume_text)

        # Run DeterministicOrchestrator processing with universal open-domain enabled
        logger.info(
            f"Running Friction AI analysis for sender {_mask_email(sender_email)} "
            f"against role: {target_role} (resume chars: {len(resume_text)})"
        )
        analysis_payload = {
            "resume": resume_text,
            "jd_text": target_jd,
            "jdText": target_jd,
            "includeRoadmap": True,
            "enableOpenDomain": True,
        }
        analysis_result = await orchestrator.process(analysis_payload)

        # If analysis_result is Pydantic model, convert to dict
        if hasattr(analysis_result, "dict"):
            analysis_data = analysis_result.dict()
        elif hasattr(analysis_result, "model_dump"):
            analysis_data = analysis_result.model_dump()
        else:
            analysis_data = dict(analysis_result)

        # Enrich cross-domain mismatch replies with a transition roadmap when available
        if str(analysis_data.get("status") or "").lower() == "domain_mismatch" and hasattr(orchestrator, "generate_transition_analysis"):
            try:
                transition_res = await orchestrator.generate_transition_analysis(
                    resume=resume_text,
                    jd=target_jd,
                    resume_domain=str(analysis_data.get("resume_domain") or "Current Background"),
                    jd_domain=str(analysis_data.get("jd_domain") or target_role),
                )
                if isinstance(transition_res, dict) and transition_res.get("roadmap"):
                    analysis_data["roadmap"] = transition_res["roadmap"]
            except Exception as tr_err:
                logger.warning(f"Transition roadmap generation skipped on domain_mismatch: {tr_err}")

        # Generate Frontend-Parity HTML Email Report
        html_report = self.generate_professional_html_report(
            candidate_name=candidate_name,
            target_role=target_role,
            analysis=analysis_data,
            matched_from_sharepoint=matched_from_sharepoint,
            sharepoint_source_file=sharepoint_source_file,
        )

        # Send Reply Email via Microsoft Graph
        email_sent = False
        if settings.outlook_auto_reply_enabled and sender_email:
            reply_subject = f"Your Talent Evaluation & Roadmap: {target_role}"
            email_sent = await self.send_reply_email(
                to_address=sender_email,
                subject=reply_subject,
                html_body=html_report,
            )

        # Mark as read ONLY when reply succeeded (or auto-reply disabled) to prevent silent dropped applications
        if settings.outlook_mark_as_read and (email_sent or not settings.outlook_auto_reply_enabled or not sender_email):
            await self.mark_message_as_read(message_id)

        return {
            "messageId": message_id,
            "status": "processed",
            "sender": sender_email,
            "candidateName": candidate_name,
            "sourceFile": source_name,
            "overallScore": analysis_data.get("overall_score") or analysis_data.get("overallScore"),
            "emailSent": email_sent,
            "matchedFromSharePoint": matched_from_sharepoint,
            "sharepointFile": sharepoint_source_file,
        }

    @staticmethod
    async def _try_claim_message_lock(message_id: Optional[str]) -> bool:
        """Atomically claim a message in Redis so overlapping polls/workers never double-process it."""
        if not message_id:
            return True
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            if not r:
                return True
            claimed = await r.set(f"outlook:lock:{message_id}", "1", nx=True, ex=300)
            return bool(claimed)
        except Exception as e:
            logger.debug(f"Redis lock fallback (allowing process): {e}")
            return True

    @staticmethod
    async def _record_poison_pill_failure(message_id: Optional[str]) -> int:
        """Track failed processing attempts per message so poison pills stop burning LLM quota."""
        if not message_id:
            return 1
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            if not r:
                return 1
            key = f"outlook:retries:{message_id}"
            count = await r.incr(key)
            await r.expire(key, 86400)
            return int(count)
        except Exception:
            return 1

    @staticmethod
    async def _try_acquire_poll_leader() -> bool:
        """Best-effort distributed poll-tick lease across multi-worker deployments."""
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            if not r:
                return True
            return bool(await r.set("outlook:poller:leader", "1", nx=True, ex=45))
        except Exception:
            return True

    @staticmethod
    async def _release_poll_leader() -> None:
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            if r:
                await r.delete("outlook:poller:leader")
        except Exception:
            pass

    async def poll_and_process_inbox(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        High-level polling orchestrator with single-flight lock, Redis distributed leader & message claim,
        background LLM priority yielding, and poison-pill failure caps.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Outlook service not configured.",
                "processedCount": 0,
            }

        async with self._get_poll_lock():
            if not await self._try_acquire_poll_leader():
                return {
                    "success": True,
                    "message": "Another worker holds the active Outlook poll lease.",
                    "processedCount": 0,
                    "results": [],
                }
            try:
                poll_limit = limit or settings.outlook_poll_limit
                unread_emails = await self.fetch_unread_candidate_emails(limit=poll_limit)

                if not unread_emails:
                    return {
                        "success": True,
                        "message": "Inbox has no unread candidate emails.",
                        "processedCount": 0,
                        "results": [],
                    }

                from app.ai.client import llm_priority_ctx
                from app.ai.orchestrator import DeterministicOrchestrator
                orchestrator = DeterministicOrchestrator()

                results = []
                priority_token = llm_priority_ctx.set("background")
                try:
                    for idx, msg in enumerate(unread_emails):
                        msg_id = msg.get("id")
                        if not await self._try_claim_message_lock(msg_id):
                            logger.info(f"Skipping message {msg_id}: already claimed by active worker.")
                            continue
                        try:
                            res = await self.process_candidate_message(msg, orchestrator)
                            results.append(res)
                            # Inter-email pacing prevents back-to-back TPM bursts on multi-email poll batches
                            if idx + 1 < len(unread_emails) and res.get("status") == "processed":
                                await asyncio.sleep(3.0)
                        except Exception as e:
                            fail_count = await self._record_poison_pill_failure(msg_id)
                            logger.error(f"Error processing message {msg_id} (attempt {fail_count}/3): {e}")
                            if fail_count >= 3 and settings.outlook_mark_as_read and msg_id:
                                logger.warning(f"Poison-pill quarantine: marking message {msg_id} as read after {fail_count} failures.")
                                try:
                                    await self.mark_message_as_read(msg_id)
                                except Exception:
                                    pass
                            results.append({
                                "messageId": msg_id,
                                "status": "error",
                                "error": str(e),
                                "attempt": fail_count,
                            })
                finally:
                    llm_priority_ctx.reset(priority_token)

                return {
                    "success": True,
                    "processedCount": len(results),
                    "results": results,
                }
            finally:
                await self._release_poll_leader()

    async def start_background_listener(self, stop_event: Any) -> None:
        """
        Continuously poll the Outlook mailbox at configured intervals in the background.
        Caps automated per-tick batches to protect shared LLM RPM/TPM limits.
        """
        interval = getattr(settings, "outlook_poll_interval_seconds", 45)
        bg_batch_limit = min(getattr(settings, "outlook_poll_limit", 10), 3)
        logger.info(
            f"Autonomous Outlook HR background poller started for '{self.mailbox_email}' "
            f"(interval: {interval}s, max batch/tick: {bg_batch_limit})."
        )

        while not (hasattr(stop_event, "is_set") and stop_event.is_set()):
            if not self._poller_paused:
                try:
                    summary = await self.poll_and_process_inbox(limit=bg_batch_limit)
                    count = summary.get("processedCount", 0)
                    if count > 0:
                        logger.info(f"Autonomous Outlook Poller processed {count} candidate resume(s).")
                except Exception as e:
                    logger.error(f"Transient error in Outlook background poller: {e}")

            # Sleep in 1-second ticks so server shutdown cancels immediately without lag
            for _ in range(int(interval)):
                if hasattr(stop_event, "is_set") and stop_event.is_set():
                    break
                await asyncio.sleep(1)

        logger.info("Autonomous Outlook HR background poller terminated cleanly.")


# Singleton instance
outlook_service = OutlookService()
