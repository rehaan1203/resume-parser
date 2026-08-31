"""Tests for Redis client."""
import pytest
from app.core.cache.redis_client import RedisClient
from app.config import settings

@pytest.mark.asyncio
async def test_redis_connection():
    """Test Redis connection."""
    client = RedisClient()
    
    # Test ping
    is_available = await client.ping()
    
    if settings.redis_url:
        assert is_available is True
    else:
        assert is_available is False

@pytest.mark.asyncio
async def test_redis_client_singleton():
    """Test Redis client is singleton."""
    client1 = RedisClient()
    client2 = RedisClient()
    
    assert client1 is client2

@pytest.mark.asyncio
async def test_redis_is_available():
    """Test is_available method."""
    client = RedisClient()
    available = client.is_available()
    
    if settings.redis_url and settings.cache_enabled:
        assert available is True
    else:
        assert available is False

@pytest.mark.asyncio
async def test_get_client():
    """Test getting Redis client."""
    client = RedisClient()
    redis_client = await client.get_client()
    
    if settings.redis_url and settings.cache_enabled:
        assert redis_client is not None
    else:
        assert redis_client is None
