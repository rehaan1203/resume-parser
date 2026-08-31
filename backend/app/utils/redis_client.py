"""Redis Cloud connection manager with connection pooling."""
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from typing import Optional
import json
from app.config import settings
from app.utils.logger import logger

class RedisClient:
    """Singleton Redis client with connection pooling."""
    
    _instance: Optional['RedisClient'] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._setup_pool()
    
    def _setup_pool(self):
        """Set up Redis connection pool."""
        try:
            if not settings.redis_url:
                logger.warning("REDIS_URL not configured")
                self._client = None
                return
                
            self._pool = ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_size,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                decode_responses=True
            )
            self._client = redis.Redis(connection_pool=self._pool)
            logger.info("Redis connection pool established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._client = None
    
    async def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client instance."""
        if not self._client:
            logger.warning("Redis client not available")
            return None
        return self._client
    
    async def ping(self) -> bool:
        """Check Redis connectivity."""
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.disconnect()
            logger.info("Redis connection pool closed")
    
    def is_available(self) -> bool:
        """Check if Redis is configured and available."""
        return bool(settings.redis_url and self._client)
