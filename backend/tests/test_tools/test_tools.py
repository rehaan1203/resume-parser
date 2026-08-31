import pytest
from app.core.tools.privacy import scrub_pii
from app.core.tools.url_fetcher import URLFetcher
from app.core.tools.pdf_parser import PDFParser

def test_privacy_scrub_pii():
    text = "Contact me at test@example.com or 555-123-4567. See my linkedin.com/in/testuser. I live at 123 Main St."
    scrubbed = scrub_pii(text)
    
    assert "test@example.com" not in scrubbed
    assert "[EMAIL]" in scrubbed
    assert "555-123-4567" not in scrubbed
    assert "[PHONE]" in scrubbed
    assert "linkedin.com/in/testuser" not in scrubbed
    assert "[LINKEDIN]" in scrubbed
    assert "123 Main St" not in scrubbed
    assert "[ADDRESS]" in scrubbed

@pytest.mark.asyncio
async def test_url_fetcher_initialization():
    fetcher = URLFetcher()
    assert fetcher is not None

@pytest.mark.asyncio
async def test_pdf_parser_initialization():
    parser = PDFParser()
    assert parser is not None
