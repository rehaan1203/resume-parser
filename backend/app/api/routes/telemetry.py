"""Resource click telemetry and engagement tracking API routes."""
from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import json
from datetime import datetime, timezone
from app.utils.logger import logger
from app.utils.datetime_utils import get_utc_timestamp

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])

# Resilient in-memory fallback store
IN_MEMORY_CLICK_COUNTS: Dict[str, int] = {}
IN_MEMORY_DOMAIN_COUNTS: Dict[str, int] = {}

class ResourceClickEvent(BaseModel):
    resource_id: Optional[str] = Field(None, description="Unique ID of the verified resource if available")
    resource_url: str = Field(..., description="Destination URL clicked by the candidate")
    title: Optional[str] = Field(None, description="Title of the resource")
    domain: Optional[str] = Field("tech", description="Career track/domain")
    source: Optional[str] = Field("roadmap", description="Component origin (roadmap, transition, interview)")

@router.post(
    "/resource-click",
    status_code=status.HTTP_200_OK,
    summary="Record verified resource click event"
)
async def record_resource_click(event: ResourceClickEvent):
    """
    Log candidate interaction with a learning resource.
    Used for popularity boosting and link engagement ranking.
    """
    identifier = event.resource_id or event.resource_url.strip()
    domain = (event.domain or "tech").lower()

    # 1. Update in-memory tracker
    IN_MEMORY_CLICK_COUNTS[identifier] = IN_MEMORY_CLICK_COUNTS.get(identifier, 0) + 1
    IN_MEMORY_DOMAIN_COUNTS[domain] = IN_MEMORY_DOMAIN_COUNTS.get(domain, 0) + 1
    total_clicks = IN_MEMORY_CLICK_COUNTS[identifier]

    # 2. Update Redis telemetry if available
    try:
        from app.utils.redis_client import RedisClient
        redis = RedisClient()
        client = await redis.get_client()
        if client:
            # Increment resource click counter
            await client.incr(f"friction:telemetry:clicks:{identifier}")
            # Increment sorted set for popular resources
            await client.zincrby("friction:telemetry:popular", 1, identifier)
            # Increment domain counter
            await client.incr(f"friction:telemetry:domain:{domain}")
            # Log click event into a recent audit list (capped to last 1000 events)
            audit_entry = json.dumps({
                "identifier": identifier,
                "url": event.resource_url,
                "title": event.title,
                "domain": domain,
                "timestamp": get_utc_timestamp()
            })
            await client.lpush("friction:telemetry:events", audit_entry)
            await client.ltrim("friction:telemetry:events", 0, 999)
    except Exception as e:
        logger.debug(f"Redis telemetry write skipped: {e}")

    logger.info(f"📊 Recorded click event for resource '{event.title or identifier}' in domain '{domain}' (total: {total_clicks})")
    return {
        "status": "recorded",
        "identifier": identifier,
        "clicks": total_clicks,
        "timestamp": get_utc_timestamp()
    }

@router.get(
    "/popular",
    status_code=status.HTTP_200_OK,
    summary="Get most engaged learning resources"
)
async def get_popular_resources(limit: int = 10):
    """
    Retrieve top clicked verified resources by candidate engagement.
    """
    try:
        from app.utils.redis_client import RedisClient
        redis = RedisClient()
        client = await redis.get_client()
        if client and await redis.ping():
            popular_raw = await client.zrevrange("friction:telemetry:popular", 0, limit - 1, withscores=True)
            if popular_raw:
                return {
                    "source": "redis",
                    "popular": [
                        {"identifier": k.decode("utf-8") if isinstance(k, bytes) else str(k), "clicks": int(score)}
                        for k, score in popular_raw
                    ]
                }
    except Exception:
        pass

    # Fallback to in-memory popular counts
    sorted_mem = sorted(IN_MEMORY_CLICK_COUNTS.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {
        "source": "memory",
        "popular": [{"identifier": k, "clicks": v} for k, v in sorted_mem]
    }

async def get_resource_popularity_clicks(resource_id: str) -> int:
    """Helper to fetch total clicks for a resource to compute ranking boost."""
    # Check in-memory first
    mem_count = IN_MEMORY_CLICK_COUNTS.get(resource_id, 0)
    try:
        from app.utils.redis_client import RedisClient
        redis = RedisClient()
        client = await redis.get_client()
        if client and await redis.ping():
            raw = await client.get(f"friction:telemetry:clicks:{resource_id}")
            if raw:
                redis_count = int(raw)
                return max(mem_count, redis_count)
    except Exception:
        pass
    return mem_count

