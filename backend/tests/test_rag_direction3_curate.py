"""Unit tests for Direction 3: Safe Whitelisted Resource Ingestion Tool."""
import pytest
from scripts.curate_resource import is_whitelisted_domain, add_resource_to_catalog


def test_is_whitelisted_domain_validation():
    """Verify that domain whitelist allows trusted sources and blocks untrusted/malicious domains."""
    assert is_whitelisted_domain("https://fastapi.tiangolo.com/tutorial/") is True
    assert is_whitelisted_domain("https://www.youtube.com/watch?v=123") is True
    assert is_whitelisted_domain("https://docs.python.org/3/library/") is True
    assert is_whitelisted_domain("https://law.cornell.edu/wex/contract") is True
    
    # Untrusted / spoofed domains
    assert is_whitelisted_domain("https://malicious-site.com/phishing") is False
    assert is_whitelisted_domain("https://not-youtube.com/fake") is False
    assert is_whitelisted_domain("not_a_valid_url") is False


def test_add_resource_untrusted_domain_raises():
    """Verify adding a resource from a non-whitelisted domain raises ValueError."""
    with pytest.raises(ValueError, match="not in the trusted authority whitelist"):
        add_resource_to_catalog(
            domain="tech",
            resource_id="tech-untrusted-test",
            title="Untrusted Course",
            url="https://sketchy-tutorials.biz/course",
            platform="Sketchy",
            resource_type="course",
            skills_covered=["python"],
            difficulty="beginner",
            duration_hours=2.0,
            is_free=True,
            description="Sketchy tutorial",
            bypass_probe=True
        )

