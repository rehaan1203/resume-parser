"""Tests for cached AI service."""
import pytest
from app.services.cached_ai_service import CachedAIService
from app.config import settings

@pytest.mark.asyncio
async def test_cached_service_init():
    """Test cached service initialization."""
    service = CachedAIService()
    
    assert service.ai_service is not None
    assert service.cache_manager is not None
    assert service.cache_enabled == settings.cache_enabled

@pytest.mark.asyncio
async def test_cached_analysis():
    """Test cached analysis."""
    service = CachedAIService()
    
    if not service.cache_enabled or not service.cache_manager.redis_client.is_available():
        pytest.skip("Cache not available")
    
    request = {
        "resume": "Test resume content for caching test",
        "jd_text": "Test JD content for caching test"
    }
    
    # First call - should miss cache
    result1 = await service.analyze(request)
    assert result1["cache_metadata"]["hit"] is False
    
    # Second call with same data - should hit cache
    result2 = await service.analyze(request)
    assert result2["cache_metadata"]["hit"] is True

@pytest.mark.asyncio
async def test_get_embedding_cached():
    """Test cached embedding generation."""
    service = CachedAIService()
    
    if not service.cache_enabled or not service.cache_manager.redis_client.is_available():
        pytest.skip("Cache not available")
    
    text = "Test text for embedding cache"
    
    # First call - should miss cache
    embedding1 = await service.get_embedding(text, "resume")
    assert embedding1 is not None
    
    # Second call - should hit cache
    embedding2 = await service.get_embedding(text, "resume")
    assert embedding2 is not None
    
    # Should be same embedding
    assert len(embedding1) == len(embedding2)

@pytest.mark.asyncio
async def test_invalidate_cache():
    """Test cache invalidation."""
    service = CachedAIService()
    
    if not service.cache_enabled or not service.cache_manager.redis_client.is_available():
        pytest.skip("Cache not available")
    
    # Set a test key
    test_key = "test:invalidate:123"
    await service.cache_manager.set(test_key, {"test": "data"}, ttl=60)
    
    # Verify exists
    assert await service.cache_manager.exists(test_key) is True
    
    # Invalidate pattern
    success = await service.invalidate("test:invalidate:*")
    assert success is True
    
    # Verify gone
    assert await service.cache_manager.exists(test_key) is False

@pytest.mark.asyncio
async def test_cache_stats_endpoint():
    """Test cache statistics endpoint."""
    service = CachedAIService()
    
    if not service.cache_enabled or not service.cache_manager.redis_client.is_available():
        pytest.skip("Cache not available")
    
    stats = await service.get_stats()
    
    assert "stats" in stats
    assert "size" in stats
    assert "enabled" in stats
    assert "redis_available" in stats
    assert stats["enabled"] is True
