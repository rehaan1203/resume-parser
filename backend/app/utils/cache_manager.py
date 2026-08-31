"""Core cache operations manager."""
import json
import time
from typing import Optional, Any, Dict, List
from app.utils.redis_client import RedisClient
from app.utils.cache_keys import get_stats_key
from app.config import settings
from app.utils.logger import logger

class CacheManager:
    """Manages all cache operations."""
    
    def __init__(self):
        self.redis_client = RedisClient()
        self.enabled = settings.cache_enabled
    
    async def _get_client(self):
        """Get Redis client if available."""
        if not self.enabled:
            return None
        return await self.redis_client.get_client()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        client = await self._get_client()
        if not client:
            return None
        
        try:
            value = await client.get(key)
            if value:
                await self._increment_stats("hits")
                return json.loads(value)
            else:
                await self._increment_stats("misses")
                return None
        except Exception as e:
            logger.error(f"Cache GET failed for key {key}: {e}")
            await self._increment_stats("errors")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL."""
        client = await self._get_client()
        if not client:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await client.setex(key, ttl, serialized)
            else:
                await client.set(key, serialized)
            return True
        except Exception as e:
            import traceback
            logger.error(f"Cache SET failed for key {key}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        client = await self._get_client()
        if not client:
            return False
        
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache DELETE failed for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        client = await self._get_client()
        if not client:
            return False
        
        try:
            return bool(await client.exists(key))
        except Exception as e:
            logger.error(f"Cache EXISTS failed for key {key}: {e}")
            return False
    
    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key in seconds."""
        client = await self._get_client()
        if not client:
            return -1
        
        try:
            return await client.ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL failed for key {key}: {e}")
            return -1
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        client = await self._get_client()
        if not client:
            return 0
        
        try:
            return await client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache INCR failed for key {key}: {e}")
            return 0
    
    async def _increment_stats(self, stat_type: str):
        """Increment cache statistics."""
        key = get_stats_key()
        await self.increment(f"{key}:{stat_type}")
        await self.increment(f"{key}:total_requests")
    
    async def get_stats(self) -> Dict[str, float]:
        """Get cache statistics."""
        client = await self._get_client()
        if not client:
            return {}
        
        try:
            key = get_stats_key()
            stats = {}
            for stat in ["hits", "misses", "errors", "evictions", "total_requests"]:
                value = await client.get(f"{key}:{stat}")
                stats[stat] = int(value) if value else 0
            
            # Calculate hit rate
            total = stats.get("hits", 0) + stats.get("misses", 0)
            stats["hit_rate"] = round((stats.get("hits", 0) / total * 100) if total > 0 else 0, 2)
            return stats
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    async def clear_all(self) -> bool:
        """Clear all cache entries."""
        client = await self._get_client()
        if not client:
            return False
        
        try:
            # Only clear specific prefixes, not all keys
            prefixes = ["emb:", "analysis:", "jd:", "session:", "idx:"]
            for prefix in prefixes:
                keys = await client.keys(f"{prefix}*")
                if keys:
                    await client.delete(*keys)
            # Reset stats
            await client.delete(get_stats_key())
            logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    async def get_cache_size(self) -> int:
        """Get total number of cached items."""
        client = await self._get_client()
        if not client:
            return 0
        
        try:
            prefixes = ["emb:", "analysis:", "jd:", "session:", "idx:"]
            total = 0
            for prefix in prefixes:
                keys = await client.keys(f"{prefix}*")
                total += len(keys)
            return total
        except Exception as e:
            logger.error(f"Failed to get cache size: {e}")
            return 0
    
    async def warmup(self, sample_data: Dict[str, Any]) -> int:
        """Pre-warm cache with sample data."""
        logger.info("Starting cache warmup")
        warmed = 0
        
        for key, value in sample_data.items():
            if await self.set(key, value, ttl=3600):
                warmed += 1
        
        logger.info(f"Cache warmup completed: {warmed} entries")
        return warmed
