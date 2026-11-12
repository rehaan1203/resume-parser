"""Hot-Reload Change Data Capture (CDC) Event Bus for RAG Knowledge Base.

Enables zero-downtime hot-reload of vector store and sparse BM25 indices
when the AutonomousIngestionWorker discovers new resources or the
CatalogHealthAuditor marks endpoints degraded, without restarting FastAPI.
"""
import asyncio
from typing import Dict, List, Callable, Any, Optional, Awaitable
from dataclasses import dataclass, field
from app.utils.logger import logger

@dataclass
class CDCEvent:
    event_type: str  # "RESOURCE_CREATED", "RESOURCE_UPDATED", "RESOURCE_DEPRECATED", "INDEX_INVALIDATED"
    resource_id: str
    domain: str = "general"
    tags: List[str] = field(default_factory=list)
    payload: Optional[Dict[str, Any]] = None

class CDCEventBus:
    """Asynchronous Change Data Capture event bus with pub/sub architecture."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[CDCEvent], Awaitable[None]]]] = {
            "RESOURCE_CREATED": [],
            "RESOURCE_UPDATED": [],
            "RESOURCE_DEPRECATED": [],
            "INDEX_INVALIDATED": [],
            "*": []
        }

    def subscribe(self, event_type: str, callback: Callable[[CDCEvent], Any]):
        """Register a subscriber callback for an event type (sync or async)."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"CDCEventBus: subscribed handler to '{event_type}'")

    def publish_sync(self, event: CDCEvent):
        """Publish an event synchronously to flush cache tags and notify subscribers without event loops."""
        logger.info(f"CDCEventBus: sync publishing {event.event_type} for resource '{event.resource_id}'")
        try:
            from app.knowledge.semantic_cache import get_semantic_cache
            cache = get_semantic_cache()
            tags_to_clear = list(event.tags) + [event.domain, event.resource_id]
            cache.invalidate_tags(tags_to_clear)
        except Exception as cache_err:
            logger.debug(f"CDCEventBus cache invalidation notice: {cache_err}")

        handlers = self._subscribers.get(event.event_type, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    res.close()
            except Exception as e:
                logger.error(f"CDCEventBus subscriber error for {event.event_type}: {e}")

    async def publish(self, event: CDCEvent):
        """Publish an event to all matching subscribers."""
        logger.info(f"CDCEventBus: publishing {event.event_type} for resource '{event.resource_id}'")
        
        # 1. Invalidate matching tags in semantic cache immediately
        try:
            from app.knowledge.semantic_cache import get_semantic_cache
            cache = get_semantic_cache()
            tags_to_clear = list(event.tags) + [event.domain, event.resource_id]
            cache.invalidate_tags(tags_to_clear)
        except Exception as cache_err:
            logger.debug(f"CDCEventBus cache invalidation notice: {cache_err}")

        # 2. Notify specific subscribers
        handlers = self._subscribers.get(event.event_type, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"CDCEventBus subscriber error for {event.event_type}: {e}")

_GLOBAL_CDC_BUS: Optional[CDCEventBus] = None

def get_cdc_bus() -> CDCEventBus:
    """Singleton getter for CDCEventBus."""
    global _GLOBAL_CDC_BUS
    if _GLOBAL_CDC_BUS is None:
        _GLOBAL_CDC_BUS = CDCEventBus()
    return _GLOBAL_CDC_BUS
