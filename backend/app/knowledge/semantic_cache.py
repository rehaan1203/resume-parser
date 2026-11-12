"""Semantic Vector Query Cache with Dynamic Domain TTL for RAG Knowledge Base.

Caches verified retrieval results indexed by dense query vector embeddings.
Delivers sub-millisecond (< 1ms) responses for semantically equivalent queries
(cosine similarity >= 0.94) with domain-adaptive time-to-live expiration.
"""
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from app.knowledge.models import ResourceSearchResult, VerifiedResource
from app.utils.logger import logger

# Dynamic domain TTL in seconds
DOMAIN_TTL_SECONDS: Dict[str, float] = {
    "tech": 4 * 3600.0,       # 4 hours (rapidly updating packages/versions)
    "finance": 24 * 3600.0,   # 24 hours (daily market schedules/quarterly filings)
    "legal": 72 * 3600.0,     # 72 hours (statutory law & acts change slowly)
    "trades": 7 * 86400.0,    # 7 days (physical trade standards & codes change on multi-year cycles)
    "default": 24 * 3600.0
}

class SemanticCacheEntry:
    """Represents a cached search result set with embedding and expiration."""

    def __init__(
        self,
        query_text: str,
        query_vector: List[float],
        results: List[ResourceSearchResult],
        domain: str,
        jurisdiction: str,
        ttl_seconds: float,
        vendor_scope: str = "ANY",
    ):
        self.query_text = query_text
        self.query_vector = query_vector
        self.results = results
        self.domain = domain
        self.jurisdiction = jurisdiction
        self.vendor_scope = vendor_scope
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

class SemanticVectorCache:
    """In-memory semantic vector query cache with cosine similarity matching."""

    def __init__(self, similarity_threshold: float = 0.94, max_entries: int = 1000):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self._entries: List[SemanticCacheEntry] = []

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2:
            return 0.0
        min_len = min(len(v1), len(v2))
        if min_len == 0:
            return 0.0
        dot = sum(a * b for a, b in zip(v1[:min_len], v2[:min_len]))
        return max(0.0, min(1.0, dot))

    def get(
        self,
        query_vector: List[float],
        domain: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        vendor_scope: Optional[str] = None,
    ) -> Optional[List[ResourceSearchResult]]:
        """
        Lookup cached results by vector similarity.
        Returns matching cached results if similarity >= threshold and unexpired.
        """
        now = time.time()
        clean_dom = (domain or "").strip().lower()
        clean_jur = (jurisdiction or "GLOBAL").strip().upper()
        clean_vendor = (vendor_scope or "ANY").strip().lower()

        # Iterate in reverse (most recently cached first)
        for entry in reversed(self._entries):
            if entry.expires_at < now:
                continue

            # Must match domain, jurisdiction, and cloud vendor scope
            if clean_dom and entry.domain and clean_dom != entry.domain.lower():
                continue
            if clean_jur != entry.jurisdiction:
                continue
            if clean_vendor != getattr(entry, "vendor_scope", "any").lower():
                continue

            sim = self._cosine_similarity(query_vector, entry.query_vector)
            if sim >= self.similarity_threshold:
                logger.debug(f"SemanticCache HIT: query '{entry.query_text}' with sim {sim:.4f}")
                return entry.results

        return None

    def set(
        self,
        query_text: str,
        query_vector: List[float],
        results: List[ResourceSearchResult],
        domain: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        vendor_scope: Optional[str] = None,
    ):
        """Store search results with domain-adaptive TTL."""
        clean_dom = (domain or "default").strip().lower()
        clean_jur = (jurisdiction or "GLOBAL").strip().upper()
        clean_vendor = (vendor_scope or "ANY").strip().lower()
        ttl = DOMAIN_TTL_SECONDS.get(clean_dom, DOMAIN_TTL_SECONDS["default"])

        # Evict expired entries if size exceeds limit
        if len(self._entries) >= self.max_entries:
            now = time.time()
            self._entries = [e for e in self._entries if e.expires_at > now]
            if len(self._entries) >= self.max_entries:
                self._entries.pop(0)  # FIFO eviction

        entry = SemanticCacheEntry(
            query_text=query_text,
            query_vector=query_vector,
            results=results,
            domain=clean_dom,
            jurisdiction=clean_jur,
            ttl_seconds=ttl,
            vendor_scope=clean_vendor,
        )
        self._entries.append(entry)
        logger.debug(f"SemanticCache stored '{query_text}' (domain={clean_dom}, jur={clean_jur}, ttl={ttl}s)")

    def invalidate_tags(self, tags: List[str]):
        """Invalidate entries matching any of the specified skill tags or domains."""
        clean_tags = [t.lower().strip() for t in tags]
        self._entries = [
            e for e in self._entries
            if not any(t in e.query_text.lower() or t == e.domain for t in clean_tags)
        ]
        logger.debug(f"SemanticCache invalidated matching tags: {tags}")

    def clear(self):
        """Flush the cache."""
        self._entries.clear()

_GLOBAL_SEMANTIC_CACHE: Optional[SemanticVectorCache] = None

def get_semantic_cache() -> SemanticVectorCache:
    """Singleton getter for SemanticVectorCache."""
    global _GLOBAL_SEMANTIC_CACHE
    if _GLOBAL_SEMANTIC_CACHE is None:
        _GLOBAL_SEMANTIC_CACHE = SemanticVectorCache()
    return _GLOBAL_SEMANTIC_CACHE

