"""Cache management API routes."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.utils.cache_manager import CacheManager

from app.models.api_models import (
    CacheStatsResponse,
    CacheClearResponse,
    CacheWarmupResponse,
    CacheInvalidateResponse,
    CacheKeysResponse
)
from app.utils.logger import logger

router = APIRouter()

def get_cache_manager() -> CacheManager:
    return CacheManager()


@router.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    summary="Get cache statistics"
)
async def get_cache_stats(
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """Get cache hit/miss statistics."""
    stats = await cache_manager.get_stats()
    size = await cache_manager.get_cache_size()
    return {
        "stats": stats,
        "size": size,
        "enabled": cache_manager.enabled,
        "redis_available": cache_manager.redis_client.is_available()
    }

@router.post(
    "/cache/clear",
    response_model=CacheClearResponse,
    summary="Clear all cache"
)
async def clear_cache(
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """Clear all cached data."""
    success = await cache_manager.clear_all()
    if success:
        return {"message": "Cache cleared successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )

@router.post(
    "/cache/warmup",
    response_model=CacheWarmupResponse,
    summary="Pre-warm cache with sample data"
)
async def warmup_cache():
    """Warm up cache with sample data."""
    # Instead of mock data, we could just clear the cache entirely or warm it up with real AI
    return {"status": "error", "message": "Cache warmup is not supported without mock data"}

@router.delete(
    "/cache/invalidate",
    response_model=CacheInvalidateResponse,
    summary="Invalidate cache by pattern"
)
async def invalidate_cache(
    pattern: str = Query(..., description="Cache key pattern to invalidate (e.g., 'emb:*')"),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """Invalidate cache entries matching pattern."""
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pattern parameter is required"
        )
    
    client = await cache_manager.redis_client.get_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis not available"
        )
        
    keys = await client.keys(pattern)
    if keys:
        await client.delete(*keys)
        return {"message": f"Invalidated cache entries matching: {pattern}"}
    return {"message": "No cache entries matched the pattern"}

@router.get(
    "/cache/keys",
    response_model=CacheKeysResponse,
    summary="List cache keys by prefix"
)
async def list_cache_keys(
    prefix: str = Query("", description="Key prefix to list"),
    limit: int = Query(100, description="Maximum keys to return"),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """List cache keys by prefix."""
    client = await cache_manager.redis_client.get_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis not available"
        )
    
    try:
        pattern = f"{prefix}*" if prefix else "*"
        keys = await client.keys(pattern)
        # Limit results
        if len(keys) > limit:
            keys = keys[:limit]
        return {"keys": keys, "total": len(keys), "limited": len(keys) >= limit}
    except Exception as e:
        logger.error(f"Failed to list cache keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list cache keys"
        )
