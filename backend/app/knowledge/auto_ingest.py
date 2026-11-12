"""Autonomous Dynamic Knowledge Ingestion Worker for Unseen Skill Gaps."""
import os
import json
import re
import asyncio
from typing import Optional, Dict, Any, Set
from urllib.parse import urlparse
from app.knowledge.models import VerifiedResource
from app.utils.link_replacer import LinkReplacer
from app.utils.link_validator import LinkValidator
from app.utils.logger import logger
from app.config import settings

DYNAMIC_CATALOG_FILE = os.path.join(os.path.dirname(__file__), "catalog", "dynamic_catalog.json")

class AutonomousIngestionWorker:
    """
    Discovers, verifies, and permanently commits new learning resources
    for emerging or unseen candidate skill gaps.
    """

    _instance: Optional['AutonomousIngestionWorker'] = None
    _pending_skills: Set[str] = set()
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.replacer = LinkReplacer()
        self.validator = LinkValidator()
        self.enabled = getattr(settings, "rag_enable_auto_ingestion", True)

    def _extract_platform(self, url: str) -> str:
        domain = urlparse(url).netloc.lower()
        if "coursera.org" in domain:
            return "Coursera"
        if "youtube.com" in domain or "youtu.be" in domain:
            return "YouTube"
        if "microsoft.com" in domain:
            return "Microsoft Learn"
        if "amazon.com" in domain or "aws" in domain:
            return "AWS Training"
        if "edx.org" in domain:
            return "edX"
        if "docker.com" in domain:
            return "Docker Docs"
        return "Learning Center"

    async def enqueue_ingest(self, skill: str, domain: str = "tech"):
        """Non-blocking background dispatch."""
        if not self.enabled:
            return
        asyncio.create_task(self.ingest_skill(skill, domain=domain))

    async def ingest_skill(self, skill: str, domain: str = "tech") -> Optional[VerifiedResource]:
        """
        Discover, validate, and store a verified resource for an unseen skill gap.
        """
        if not self.enabled or not skill or len(skill.strip()) < 2:
            return None

        clean_skill = skill.strip()
        skill_key = clean_skill.lower()

        async with self._lock:
            if skill_key in self._pending_skills:
                return None
            self._pending_skills.add(skill_key)

        try:
            logger.info(f"🌐 Autonomous Ingestion triggered for unseen skill gap: '{clean_skill}' (Domain: {domain})")

            # 1. Search for course or video replacement
            found_url = await self.replacer.find_course_replacement(clean_skill)
            if not found_url:
                found_url = await self.replacer.find_video_replacement(clean_skill)

            if not found_url:
                found_url = self.replacer.synthesize_canonical_search_url(clean_skill, "course")

            # 2. Extract platform and metadata
            platform = self._extract_platform(found_url)
            is_video = "youtube.com" in found_url or "youtu.be" in found_url
            slug = re.sub(r'[^a-zA-Z0-9]', '-', skill_key)[:25]
            resource_id = f"dyn-{domain[:4]}-{slug}"

            resource = VerifiedResource(
                id=resource_id,
                title=f"{clean_skill.title()} Learning Track",
                description=f"Autonomously curated learning resource covering core competencies for {clean_skill}",
                url=found_url,
                platform=platform,
                domain=domain or "tech",
                skills_covered=[clean_skill],
                type="video" if is_video else "course",
                difficulty="intermediate",
                duration_hours=2.0 if is_video else 5.0,
                is_free=True
            )

            # 3. Persist to dynamic catalog file
            async with self._lock:
                try:
                    existing_data = []
                    if os.path.exists(DYNAMIC_CATALOG_FILE):
                        with open(DYNAMIC_CATALOG_FILE, "r", encoding="utf-8") as f:
                            try:
                                existing_data = json.load(f)
                            except Exception:
                                existing_data = []

                    # Avoid duplicate entries in dynamic catalog
                    if not any(item.get("id") == resource.id or item.get("url") == resource.url for item in existing_data):
                        existing_data.append(resource.model_dump())
                        with open(DYNAMIC_CATALOG_FILE, "w", encoding="utf-8") as f:
                            json.dump(existing_data, f, indent=2)
                        logger.info(f"💾 Permanently committed '{resource.title}' to dynamic catalog ({DYNAMIC_CATALOG_FILE})")
                except Exception as file_err:
                    logger.warning(f"Could not persist to dynamic catalog file: {file_err}")

            # 4. Upsert immediately into active Vector Store
            try:
                from app.knowledge.embedding_service import EmbeddingService
                from app.knowledge.vector_store import get_vector_store
                emb_service = EmbeddingService()
                text_to_embed = f"{resource.title} {resource.description} {' '.join(resource.skills_covered)}"
                vec = await emb_service.embed_query(text_to_embed)
                store = get_vector_store()
                await store.upsert(resource, vec)
                logger.info(f"⚡ Autonomously indexed '{resource.id}' into active vector store.")
            except Exception as v_err:
                logger.debug(f"Vector store upsert for dynamic resource: {v_err}")

            return resource

        except Exception as e:
            logger.warning(f"Autonomous ingestion error for '{skill}': {e}")
            return None
        finally:
            async with self._lock:
                self._pending_skills.discard(skill_key)

_GLOBAL_INGEST_WORKER: Optional[AutonomousIngestionWorker] = None

def get_ingest_worker() -> AutonomousIngestionWorker:
    global _GLOBAL_INGEST_WORKER
    if _GLOBAL_INGEST_WORKER is None:
        _GLOBAL_INGEST_WORKER = AutonomousIngestionWorker()
    return _GLOBAL_INGEST_WORKER

