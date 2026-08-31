"""Tests for link processor."""
import pytest
from app.core.link_verification.link_processor import LinkProcessor

@pytest.mark.asyncio
async def test_process_response():
    processor = LinkProcessor()
    
    response = {
        "content": {
            "days": [
                {
                    "day": 1,
                    "action": "Complete Python basics",
                    "resources": ["https://www.coursera.org/learn/python"]
                }
            ]
        }
    }
    
    processed = await processor.process_response(response)
    # Should have processed the link
    assert "resources" in processed["content"]["days"][0]
    # The link should be valid or replaced
    assert len(processed["content"]["days"][0]["resources"]) > 0

@pytest.mark.asyncio
async def test_extract_links():
    processor = LinkProcessor()
    response = {
        "content": {
            "weeks": [
                {
                    "week": 1,
                    "focus": "Python Basics",
                    "activities": [
                        {
                            "day": 1,
                            "action": "Complete Python basics",
                            "resources": ["https://www.coursera.org/learn/python"]
                        }
                    ]
                }
            ]
        }
    }
    links = processor._extract_links_with_context(response)
    assert len(links) > 0
    assert "topic" in links[0]
    assert links[0]["topic"] == "Complete Python basics"
