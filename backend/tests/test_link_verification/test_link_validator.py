"""Tests for link validator."""
import pytest
from app.core.link_verification.link_validator import LinkValidator

@pytest.mark.asyncio
async def test_validate_working_link():
    validator = LinkValidator()
    result = await validator.validate("https://www.google.com")
    assert result["status"] == "valid"
    assert result["status_code"] == 200

@pytest.mark.asyncio
async def test_validate_broken_link():
    validator = LinkValidator()
    result = await validator.validate("https://www.this-does-not-exist-12345.com")
    assert result["status"] in ["broken", "error"]

@pytest.mark.asyncio
async def test_validate_many():
    validator = LinkValidator()
    results = await validator.validate_many([
        "https://www.google.com",
        "https://www.this-does-not-exist-12345.com"
    ])
    assert len(results) == 2
    assert "https://www.google.com" in results
