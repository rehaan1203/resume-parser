"""Vector Store implementations for the RAG Knowledge Base."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import math
import json
import numpy as np
from app.knowledge.models import VerifiedResource
from app.config import settings
from app.utils.logger import logger

class BaseVectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def upsert(self, resource: VerifiedResource, vector: List[float]) -> bool:
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        domain: Optional[str] = None,
        top_k: int = 3
    ) -> List[Tuple[VerifiedResource, float]]:
        pass

    @abstractmethod
    async def count(self) -> int:
        pass

class InMemoryVectorStore(BaseVectorStore):
    """Hermetic in-memory vector store using cosine similarity."""

    def __init__(self):
        self._entries: Dict[str, Tuple[VerifiedResource, List[float]]] = {}

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2:
            return 0.0
        # Gracefully handle length differences by aligning to common length
        min_len = min(len(v1), len(v2))
        if min_len == 0:
            return 0.0
        dot = sum(a * b for a, b in zip(v1[:min_len], v2[:min_len]))
        return max(0.0, min(1.0, dot))

    async def upsert(self, resource: VerifiedResource, vector: List[float]) -> bool:
        self._entries[resource.id] = (resource, vector)
        return True

    async def search(
        self,
        query_vector: List[float],
        domain: Optional[str] = None,
        top_k: int = 3
    ) -> List[Tuple[VerifiedResource, float]]:
        results = []
        for resource, vec in self._entries.values():
            if domain and resource.domain.lower() != domain.lower():
                continue
            sim = self._cosine_similarity(query_vector, vec)
            results.append((resource, sim))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def count(self) -> int:
        return len(self._entries)

class RedisVectorStore(BaseVectorStore):
    """
    Production vector store integrated with Redis Cloud (RediSearch / VSS).
    Supports persistent HNSW vector search with multi-worker scaling,
    and automatically falls back to InMemoryVectorStore if Redis VSS
    is not enabled or connection drops.
    """

    INDEX_NAME = "idx:friction_vss"
    DOC_PREFIX = "friction:res:"

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._memory_fallback = InMemoryVectorStore()
        self._vss_enabled = False
        self._initialized = False
        self._client = None

    async def _get_client(self):
        """Lazily initialize Redis client with raw binary capabilities."""
        if self._client is None and self.redis_url:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=False,
                    socket_timeout=getattr(settings, "redis_socket_timeout", 5.0)
                )
            except Exception as e:
                logger.warning(f"Could not connect Redis client for Vector Store: {e}")
                self._client = None
        return self._client

    async def _ensure_index(self) -> bool:
        """Create RediSearch VSS index if RediSearch is supported."""
        if self._initialized:
            return self._vss_enabled

        client = await self._get_client()
        if not client:
            self._vss_enabled = False
            self._initialized = True
            return False

        try:
            # Check if index exists
            try:
                await client.execute_command("FT.INFO", self.INDEX_NAME)
                self._vss_enabled = True
                self._initialized = True
                logger.info(f"Connected to existing Redis VSS index: {self.INDEX_NAME}")
                return True
            except Exception as info_err:
                # If index doesn't exist, create it
                if "unknown index" in str(info_err).lower() or "not found" in str(info_err).lower():
                    pass
                else:
                    raise info_err

            # Create HNSW Vector Index with tag filters
            create_cmd = [
                "FT.CREATE", self.INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", self.DOC_PREFIX,
                "SCHEMA",
                "domain", "TAG",
                "type", "TAG",
                "difficulty", "TAG",
                "is_free", "TAG",
                "title", "TEXT",
                "vector", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", "384",
                "DISTANCE_METRIC", "COSINE"
            ]
            await client.execute_command(*create_cmd)
            self._vss_enabled = True
            logger.info(f"Successfully created Redis VSS index: {self.INDEX_NAME}")
        except Exception as e:
            err_str = str(e).lower()
            if "unknown command" in err_str or "module" in err_str:
                logger.info("Redis server does not have RediSearch module loaded; using resilient in-memory fallback.")
            else:
                logger.warning(f"Redis VSS initialization error: {e}. Falling back to in-memory store.")
            self._vss_enabled = False

        self._initialized = True
        return self._vss_enabled

    async def upsert(self, resource: VerifiedResource, vector: List[float]) -> bool:
        """Upsert resource into Redis VSS and mirror in local fallback."""
        # Always mirror to memory fallback for 100% availability
        await self._memory_fallback.upsert(resource, vector)

        if not await self._ensure_index():
            return True

        client = await self._get_client()
        if not client:
            return True

        try:
            key = f"{self.DOC_PREFIX}{resource.id}".encode("utf-8")
            vec_bytes = np.array(vector, dtype=np.float32).tobytes()
            payload_json = resource.model_dump_json().encode("utf-8")

            mapping = {
                b"id": str(resource.id).encode("utf-8"),
                b"domain": str(resource.domain or "tech").lower().encode("utf-8"),
                b"type": str(resource.type or "course").lower().encode("utf-8"),
                b"difficulty": str(resource.difficulty or "intermediate").lower().encode("utf-8"),
                b"is_free": str(resource.is_free).lower().encode("utf-8"),
                b"title": str(resource.title or "").encode("utf-8"),
                b"payload": payload_json,
                b"vector": vec_bytes
            }
            await client.hset(key, mapping=mapping)
            return True
        except Exception as e:
            logger.debug(f"Redis VSS upsert error for {resource.id}: {e}")
            return True

    async def search(
        self,
        query_vector: List[float],
        domain: Optional[str] = None,
        top_k: int = 3
    ) -> List[Tuple[VerifiedResource, float]]:
        """Search vector store with hybrid score calculation."""
        if not await self._ensure_index():
            return await self._memory_fallback.search(query_vector, domain=domain, top_k=top_k)

        client = await self._get_client()
        if not client:
            return await self._memory_fallback.search(query_vector, domain=domain, top_k=top_k)

        try:
            vec_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            clean_dom = (domain or "").strip().lower()

            if clean_dom and clean_dom not in ("unknown", ""):
                query_filter = f"(@domain:{{{clean_dom}}})=>[KNN {top_k * 2} @vector $vec AS score]"
            else:
                query_filter = f"(*)=>[KNN {top_k * 2} @vector $vec AS score]"

            cmd = [
                "FT.SEARCH", self.INDEX_NAME,
                query_filter,
                "PARAMS", "2", "vec", vec_bytes,
                "SORTBY", "score", "ASC",
                "RETURN", "3", "id", "payload", "score",
                "DIALECT", "2"
            ]
            raw_res = await client.execute_command(*cmd)

            # Parse RediSearch results
            # Format: [total_results, key1, [field1, val1, ...], key2, ...]
            if not raw_res or len(raw_res) <= 1:
                return await self._memory_fallback.search(query_vector, domain=domain, top_k=top_k)

            parsed: List[Tuple[VerifiedResource, float]] = []
            for i in range(1, len(raw_res), 2):
                fields = raw_res[i + 1]
                fields_dict = {}
                for j in range(0, len(fields), 2):
                    f_name = fields[j].decode("utf-8") if isinstance(fields[j], bytes) else str(fields[j])
                    fields_dict[f_name] = fields[j + 1]

                raw_payload = fields_dict.get("payload")
                raw_score = fields_dict.get("score")

                if raw_payload:
                    payload_str = raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else str(raw_payload)
                    resource = VerifiedResource.model_validate_json(payload_str)
                    
                    # Cosine distance to similarity: similarity = 1 - (distance / 2)
                    dist = float(raw_score) if raw_score is not None else 1.0
                    sim = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                    parsed.append((resource, sim))

            parsed.sort(key=lambda x: x[1], reverse=True)
            return parsed[:top_k] if parsed else await self._memory_fallback.search(query_vector, domain=domain, top_k=top_k)

        except Exception as e:
            logger.debug(f"Redis VSS search error: {e}. Falling back to in-memory search.")
            return await self._memory_fallback.search(query_vector, domain=domain, top_k=top_k)

    async def count(self) -> int:
        """Count indexed items."""
        if self._vss_enabled:
            client = await self._get_client()
            if client:
                try:
                    info = await client.execute_command("FT.INFO", self.INDEX_NAME)
                    for k_idx in range(0, len(info) - 1, 2):
                        key_name = info[k_idx].decode("utf-8") if isinstance(info[k_idx], bytes) else str(info[k_idx])
                        if key_name == "num_docs":
                            return int(info[k_idx + 1])
                except Exception:
                    pass
        return await self._memory_fallback.count()

_GLOBAL_STORE: Optional[BaseVectorStore] = None

def get_vector_store(store_type: Optional[str] = None) -> BaseVectorStore:
    """Return the singleton vector store instance."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        target_type = store_type or getattr(settings, "rag_vector_store_type", "memory")
        if target_type == "redis" and getattr(settings, "redis_url", None):
            _GLOBAL_STORE = RedisVectorStore(settings.redis_url)
        else:
            _GLOBAL_STORE = InMemoryVectorStore()
    return _GLOBAL_STORE
