"""
Microsoft SharePoint Integration Service for Friction Matcher.

Dynamically ingests, parses, and matches Job Descriptions (JDs) stored in
a designated SharePoint folder directly in-memory (zero disk writes).
"""

import asyncio
import base64
import io
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.outlook_service import outlook_service
from app.utils.logger import logger


class SharePointService:
    """Service for interacting with Microsoft SharePoint document libraries via Microsoft Graph."""

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    _COMMON_STOPWORDS = {
        "the", "and", "for", "with", "that", "this", "from", "are", "was", "will",
        "your", "our", "you", "have", "has", "had", "not", "but", "all", "can",
        "about", "into", "over", "more", "than", "their", "they", "who", "what",
        "when", "where", "which", "work", "working", "team", "role", "position",
        "job", "description", "candidate", "experience", "skills", "required",
        "responsibilities", "requirements", "ability", "strong", "good", "using",
        "years", "year", "plus", "etc", "including", "across", "within", "such",
    }

    def __init__(
        self,
        site_url: Optional[str] = None,
        folder_path: Optional[str] = None,
        cache_ttl_seconds: Optional[int] = None,
    ):
        self.site_url = site_url if site_url is not None else settings.sharepoint_site_url
        self.folder_path = folder_path if folder_path is not None else settings.sharepoint_folder_path
        self.cache_ttl_seconds = (
            cache_ttl_seconds if cache_ttl_seconds is not None else settings.sharepoint_jd_cache_ttl_seconds
        )
        self._cached_jds: List[Dict[str, Any]] = []
        self._last_cache_time: float = 0.0
        self._local_jd_version: Optional[str] = None
        self._cache_lock: Optional[asyncio.Lock] = None
        self._site_id: Optional[str] = None
        self._drive_id: Optional[str] = None

    def _get_cache_lock(self) -> asyncio.Lock:
        if self._cache_lock is None:
            self._cache_lock = asyncio.Lock()
        return self._cache_lock

    @staticmethod
    async def _get_redis_jd_version() -> Optional[str]:
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            return await r.get("sharepoint:jd_version") if r else None
        except Exception:
            return None

    @staticmethod
    async def _bump_redis_jd_version(version_val: str) -> None:
        try:
            from app.utils.redis_client import RedisClient
            r = await RedisClient().get_client()
            if r:
                await r.set("sharepoint:jd_version", version_val, ex=86400)
        except Exception:
            pass

    def is_configured(self) -> bool:
        """Verify if SharePoint site URL and Azure credentials are configured."""
        return bool(self.site_url and outlook_service.is_configured())

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Obtain authorization headers via the shared MSAL token client."""
        token = await outlook_service.acquire_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _parse_site_url(self) -> Tuple[str, str]:
        """
        Parse the configured SharePoint site URL into hostname and server-relative path.
        Example:
            https://sstlab.sharepoint.com/sites/HR -> ('sstlab.sharepoint.com', 'sites/HR')
        """
        if not self.site_url:
            raise ValueError("SHAREPOINT_SITE_URL is not configured.")

        parsed = urlparse(self.site_url)
        hostname = parsed.netloc
        relative_path = parsed.path.strip("/")
        return hostname, relative_path

    async def resolve_site_and_drive(self) -> Tuple[str, str]:
        """
        Query Microsoft Graph to resolve the SharePoint site ID and default Drive ID.
        Caches IDs in memory for the lifecycle of the service.
        """
        if self._site_id and self._drive_id:
            return self._site_id, self._drive_id

        hostname, relative_path = self._parse_site_url()
        headers = await self._get_auth_headers()

        # 1. Resolve Site ID
        if relative_path:
            site_endpoint = f"{self.GRAPH_BASE_URL}/sites/{hostname}:/{relative_path}"
        else:
            site_endpoint = f"{self.GRAPH_BASE_URL}/sites/{hostname}"

        site_resp = await outlook_service._graph_request("GET", site_endpoint, headers=headers)
        if site_resp.status_code != 200:
            logger.error(f"Failed to resolve SharePoint site '{self.site_url}': {site_resp.text}")
            raise ConnectionError(f"SharePoint site resolution failed ({site_resp.status_code}): {site_resp.text}")

        site_data = site_resp.json()
        self._site_id = site_data.get("id")

        # 2. Resolve default Document Library Drive ID
        drive_endpoint = f"{self.GRAPH_BASE_URL}/sites/{self._site_id}/drive"
        drive_resp = await outlook_service._graph_request("GET", drive_endpoint, headers=headers)
        if drive_resp.status_code == 200:
            self._drive_id = drive_resp.json().get("id")
        else:
            # Fallback: list all drives and pick first Document Library
            drives_list_resp = await outlook_service._graph_request("GET", f"{self.GRAPH_BASE_URL}/sites/{self._site_id}/drives", headers=headers)
            if drives_list_resp.status_code == 200 and drives_list_resp.json().get("value"):
                self._drive_id = drives_list_resp.json()["value"][0].get("id")
            else:
                raise ConnectionError("Could not resolve Document Library Drive ID for SharePoint site.")

        logger.info(f"Resolved SharePoint Site ID: {self._site_id} | Drive ID: {self._drive_id}")
        return self._site_id, self._drive_id

    async def test_connection(self) -> Dict[str, Any]:
        """Test SharePoint credentials, site access, and folder visibility."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "SharePoint service is not configured in settings or environment.",
                "siteUrl": self.site_url,
            }

        try:
            site_id, drive_id = await self.resolve_site_and_drive()
            jds = await self.fetch_active_job_descriptions(force_refresh=True)
            return {
                "success": True,
                "siteUrl": self.site_url,
                "folderPath": self.folder_path,
                "siteId": site_id,
                "driveId": drive_id,
                "activeJdCount": len(jds),
                "activeJobs": [j["title"] for j in jds],
            }
        except Exception as e:
            logger.error(f"SharePoint test connection error: {e}")
            return {
                "success": False,
                "error": str(e),
                "siteUrl": self.site_url,
            }

    async def fetch_active_job_descriptions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieve all active JDs from the configured SharePoint folder (supports @odata.nextLink pagination).
        Extracts content in-memory (DOCX paragraphs+tables, PDF, TXT, DOC fallback) and caches cleanly.
        """
        now = time.time()
        remote_version = await self._get_redis_jd_version() if not force_refresh else None
        version_stale = bool(remote_version and remote_version != self._local_jd_version)

        if (
            not force_refresh
            and not version_stale
            and self._cached_jds
            and (now - self._last_cache_time < self.cache_ttl_seconds)
        ):
            return self._cached_jds

        if not self.is_configured():
            logger.info("SharePoint not configured. No external JDs to fetch.")
            return []

        async with self._get_cache_lock():
            now = time.time()
            remote_version = await self._get_redis_jd_version() if not force_refresh else None
            version_stale = bool(remote_version and remote_version != self._local_jd_version)
            if (
                not force_refresh
                and not version_stale
                and self._cached_jds
                and (now - self._last_cache_time < self.cache_ttl_seconds)
            ):
                return self._cached_jds

            try:
                _, drive_id = await self.resolve_site_and_drive()
                headers = await self._get_auth_headers()

                clean_folder = self.folder_path.strip("/")
                if "://" in clean_folder:
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(clean_folder)
                    unquoted_path = urllib.parse.unquote(parsed_url.path)
                    match = re.search(r'(?:shared\s+documents|documents)/(.*)$', unquoted_path, re.IGNORECASE)
                    if match:
                        clean_folder = match.group(1).strip("/")
                    else:
                        clean_folder = unquoted_path.strip("/").split("/")[-1]

                if clean_folder.lower().startswith("shared documents/"):
                    clean_folder = clean_folder[len("shared documents/"):]
                elif clean_folder.lower() == "shared documents":
                    clean_folder = ""

                from urllib.parse import quote
                if clean_folder:
                    encoded_folder = quote(clean_folder, safe="/")
                    next_url: Optional[str] = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/root:/{encoded_folder}:/children"
                else:
                    next_url = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/root/children"

                items: List[Dict[str, Any]] = []
                while next_url:
                    resp = await outlook_service._graph_request("GET", next_url, headers=headers)
                    if resp.status_code != 200:
                        if resp.status_code in (404, 410):
                            self._site_id = None
                            self._drive_id = None
                        logger.warning(f"Could not list SharePoint folder '{self.folder_path}': {resp.status_code} - {resp.text}")
                        return self._cached_jds
                    data = resp.json()
                    items.extend(data.get("value", []))
                    next_url = data.get("@odata.nextLink")

                max_file_bytes = getattr(settings, "max_download_size_bytes", 15 * 1024 * 1024)
                loaded_jds: List[Dict[str, Any]] = []
                for item in items:
                    name = item.get("name", "")
                    item_id = item.get("id")
                    download_url = item.get("@microsoft.graph.downloadUrl")
                    reported_size = item.get("size") or 0
                    if reported_size and reported_size > max_file_bytes:
                        logger.warning(f"Skipping oversized SharePoint JD '{name}' ({reported_size} bytes > {max_file_bytes}).")
                        continue

                    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
                    if ext not in ["docx", "doc", "pdf", "txt"]:
                        continue

                    file_bytes = None
                    if download_url:
                        dl_resp = await outlook_service._graph_request("GET", download_url)
                        if dl_resp.status_code == 200:
                            file_bytes = dl_resp.content
                    if not file_bytes and item_id:
                        content_url = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content"
                        dl_resp = await outlook_service._graph_request("GET", content_url, headers=headers)
                        if dl_resp.status_code == 200:
                            file_bytes = dl_resp.content

                    if not file_bytes:
                        continue
                    if len(file_bytes) > max_file_bytes:
                        logger.warning(f"Skipping downloaded oversized SharePoint JD '{name}' ({len(file_bytes)} bytes).")
                        continue

                    jd_text = await asyncio.to_thread(self._extract_jd_text_in_memory, file_bytes, ext, name)
                    if len(jd_text.strip()) >= 50:
                        cleaned_txt = jd_text.strip()
                        job_title = self._clean_job_title(name, cleaned_txt)
                        raw_tokens = set(re.findall(r"[a-z0-9\+\#]{2,}", cleaned_txt.lower()))
                        loaded_jds.append({
                            "id": item_id,
                            "filename": name,
                            "title": job_title,
                            "text": cleaned_txt,
                            "title_tokens": set(re.findall(r"[a-z0-9\+\#]+", job_title.lower())),
                            "text_tokens": raw_tokens - self._COMMON_STOPWORDS,
                            "lastModified": item.get("lastModifiedDateTime"),
                            "size": item.get("size", len(file_bytes)),
                        })
                        logger.info(f"Loaded SharePoint JD in-memory: '{job_title}' ({name})")

                self._cached_jds = loaded_jds
                self._last_cache_time = time.time()
                if force_refresh or not remote_version:
                    new_ver = str(int(self._last_cache_time * 1000))
                    self._local_jd_version = new_ver
                    await self._bump_redis_jd_version(new_ver)
                else:
                    self._local_jd_version = remote_version
                logger.info(f"Successfully cached {len(loaded_jds)} active JDs from SharePoint.")
                return self._cached_jds

            except Exception as e:
                logger.error(f"Error fetching JDs from SharePoint: {e}")
                return self._cached_jds

    def _extract_jd_text_in_memory(self, raw_bytes: bytes, ext: str, filename: str) -> str:
        """Parse raw file bytes in memory without touching disk storage (includes DOCX tables + DOC fallback)."""
        if ext == "docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(raw_bytes))
                parts = [p.text for p in doc.paragraphs if p.text.strip()]
                for table in doc.tables:
                    for row in table.rows:
                        row_txt = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                        if row_txt:
                            parts.append(row_txt)
                return "\n".join(parts)
            except Exception as e:
                logger.warning(f"Error parsing DOCX JD '{filename}': {e}")

        elif ext == "doc":
            txt = outlook_service._extract_legacy_doc_fallback(raw_bytes)
            if len(txt.strip()) >= 80:
                return txt
            logger.warning(f"Legacy binary .doc JD '{filename}' yielded insufficient text; please convert to .docx or .pdf.")

        elif ext == "pdf":
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
                    text = "\n".join(pages)
                    if len(text.strip()) >= 50:
                        return text
            except Exception as e:
                logger.warning(f"pdfplumber failed for '{filename}': {e}")

            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception as e:
                logger.warning(f"PyPDF2 failed for '{filename}': {e}")

        elif ext == "txt":
            try:
                return raw_bytes.decode("utf-8", errors="ignore")
            except Exception:
                pass

        return ""

    def _clean_job_title(self, filename: str, jd_text: str) -> str:
        """Extract a readable Job Title from filename or document header."""
        # Clean filename: "Senior_Python_Backend_Developer_JD.docx" -> "Senior Python Backend Developer"
        base = filename.rsplit(".", 1)[0]
        base = re.sub(r"[_\-\.]+", " ", base)
        base = re.sub(r"\b(jd|job|description|spec|final|v\d+)\b", "", base, flags=re.IGNORECASE).strip()
        title_case = " ".join(word.capitalize() for word in base.split())
        return title_case or "Active Requisition"

    async def find_best_matching_jd(
        self,
        candidate_resume_text: str,
        preferred_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Identify the most appropriate SharePoint JD for the candidate:
        1. If preferred_role is specified (from subject/body), matches against JD titles.
        2. If open application, compares resume text against all SharePoint JDs and selects top match.
        """
        jds = await self.fetch_active_job_descriptions()
        if not jds:
            return {"found": False, "reason": "No active JDs in SharePoint folder."}

        # Case 1: Candidate targeted a specific role
        if preferred_role and len(preferred_role.strip()) > 3:
            role_norm = re.sub(r"^(?:\s*(?:re|fwd|fw)\s*:\s*)+", "", preferred_role.strip(), flags=re.IGNORECASE).lower()
            best_role_match = None
            highest_overlap = 0.0

            noise_tokens = self._COMMON_STOPWORDS | {
                "the", "a", "an", "for", "application", "applying", "applied",
                "role", "position", "job", "senior", "lead", "junior",
                "resume", "cv", "profile", "attached", "attachment", "please", "find",
            }
            target_tokens = set(re.findall(r"[a-z0-9\+\#]+", role_norm)) - noise_tokens

            for jd in jds:
                title_tokens = jd.get("title_tokens") or set(re.findall(r"[a-z0-9\+\#]+", jd["title"].lower()))
                if not target_tokens:
                    continue
                intersection = target_tokens.intersection(title_tokens)
                score = len(intersection) / len(target_tokens)
                if score > highest_overlap:
                    highest_overlap = score
                    best_role_match = jd

            if best_role_match and highest_overlap >= 0.3:
                logger.info(f"Matched role '{preferred_role}' to SharePoint JD '{best_role_match['title']}' (score: {highest_overlap:.2f})")
                return {
                    "found": True,
                    "job_title": best_role_match["title"],
                    "jd_text": best_role_match["text"],
                    "source_file": best_role_match["filename"],
                    "match_confidence": highest_overlap,
                    "selection_mode": "role_specified",
                }

        # Case 2: Open application - Best Fit Across All JDs (stopword-filtered domain/skill affinity)
        resume_tokens = set(re.findall(r"[a-z0-9\+\#]{2,}", candidate_resume_text.lower())) - self._COMMON_STOPWORDS
        best_jd = None
        best_score = -1.0

        for jd in jds:
            jd_tokens = (
                jd.get("text_tokens")
                or (set(re.findall(r"[a-z0-9\+\#]{2,}", jd["text"].lower())) - self._COMMON_STOPWORDS)
            )
            if not jd_tokens:
                continue
            common = resume_tokens.intersection(jd_tokens)
            # Blended coverage score prevents short JDs from beating detailed descriptions
            jd_cov = len(common) / (len(jd_tokens) + 1e-6)
            res_cov = len(common) / (len(resume_tokens) + 1e-6) if resume_tokens else 0.0
            score = 0.6 * jd_cov + 0.4 * res_cov
            if score > best_score:
                best_score = score
                best_jd = jd

        if best_jd and best_score >= 0.08:
            logger.info(f"Auto-matched candidate resume to top SharePoint JD: '{best_jd['title']}' (score: {best_score:.3f})")
            return {
                "found": True,
                "job_title": best_jd["title"],
                "jd_text": best_jd["text"],
                "source_file": best_jd["filename"],
                "match_confidence": round(best_score, 3),
                "selection_mode": "best_fit_routed",
            }

        return {"found": False, "reason": "No SharePoint JD met minimum skill/domain relevance threshold."}


# Singleton instance
sharepoint_service = SharePointService()

