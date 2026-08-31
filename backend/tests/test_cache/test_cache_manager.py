"""Tests for cache manager."""
import pytest
from app.core.cache.cache_manager import CacheManager
from app.config import settings

@pytest.mark.asyncio
async def test_cache_set_get():
    """Test cache set and get."""
    cache = CacheManager()
    
    if not cache.enabled or not cache.redis_client.is_available():
        pytest.skip("Cache not available")
    
    key = "test:key"
    value = {"test": "data", "number": 123}
    
    # Set value
    success = await cache.set(key, value, ttl=10)
    assert success is True
    
    # Get value
    retrieved = await cache.get(key)
    assert retrieved == value
    
    # Clean up
    await cache.delete(key)

@pytest.mark.asyncio
async def test_cache_exists():
    """Test cache exists check."""
    cache = CacheManager()
    
    if not cache.enabled or not cache.redis_client.is_available():
        pytest.skip("Cache not available")
    
    key = "test:exists"
    
    # Should not exist initially
    assert await cache.exists(key) is False
    
    # Set value
    await cache.set(key, {"data": "test"}, ttl=10)
    
    # Should exist now
    assert await cache.exists(key) is True
    
    # Clean up
    await cache.delete(key)

@pytest.mark.asyncio
async def test_cache_ttl():
    """Test cache TTL."""
    cache = CacheManager()
    
    if not cache.enabled or not cache.redis_client.is_available():
        pytest.skip("Cache not available")
    
    key = "test:ttl"
    
    # Set with TTL
    await cache.set(key, {"data": "test"}, ttl=60)
    
    # Check TTL
    ttl = await cache.get_ttl(key)
    assert 0 < ttl <= 60
    
    # Clean up
    await cache.delete(key)

@pytest.mark.asyncio
async def test_cache_stats():
    """Test cache statistics."""
    cache = CacheManager()
    
    if not cache.enabled or not cache.redis_client.is_available():
        pytest.skip("Cache not available")
    
    key = "test:stats"
    
    # Get initial stats
    initial_stats = await cache.get_stats()
    
    # Perform operations
    await cache.get("nonexistent_key")  # Miss
    await cache.set(key, {"data": "test"}, ttl=10)  # Set
    await cache.get(key)  # Hit
    
    # Get updated stats
    updated_stats = await cache.get_stats()
    
    # Check stats increased
    assert updated_stats.get("hits", 0) > initial_stats.get("hits", 0)
    assert updated_stats.get("misses", 0) > initial_stats.get("misses", 0)
    
    # Clean up
    await cache.delete(key)

@pytest.mark.asyncio
async def test_cache_clear():
    """Test cache clear."""
    cache = CacheManager()
    
    if not cache.enabled or not cache.redis_client.is_available():
        pytest.skip("Cache not available")
    
    # Set multiple values
    for i in range(3):
        await cache.set(f"test:clear:{i}", {"data": i}, ttl=60)
    
    # Clear cache
    success = await cache.clear_all()
    assert success is True
    
    # Verify cleared
    size = await cache.get_cache_size()
    assert size == 0
