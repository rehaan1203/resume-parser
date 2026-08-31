"""Tests for link replacer."""
import pytest
from app.core.link_verification.link_replacer import LinkReplacer

@pytest.mark.asyncio
async def test_find_course_replacement():
    replacer = LinkReplacer()
    result = await replacer.find_course_replacement("Python programming")
    if result:
        assert result.startswith("http")
        # Should be a valid link
        assert await replacer._quick_verify(result) is True

@pytest.mark.asyncio
async def test_find_video_replacement():
    replacer = LinkReplacer()
    result = await replacer.find_video_replacement("Python tutorial")
    if result:
        assert result.startswith("http")
        assert "youtube.com" in result
