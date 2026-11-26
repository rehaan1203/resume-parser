"""PDF parsing for resume extraction."""
import io
from typing import Optional, Dict, List
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader
import pdfplumber
from app.utils.logger import logger

class PDFParser:
    """Extract text and structure from PDF resumes."""
    
    async def extract_text(self, pdf_bytes: bytes) -> Optional[str]:
        """Extract text from PDF bytes using pdfplumber with PyPDF2 fallback."""
        text_parts = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts and any(len(p.strip()) > 0 for p in text_parts):
                extracted = "\n".join(text_parts).strip()
                logger.info(f"PDF extraction successful (pdfplumber): {len(extracted)} chars")
                return extracted
        except Exception as e:
            logger.warning(f"pdfplumber extraction error: {e}. Falling back to PyPDF2...")

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            fallback_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    fallback_parts.append(page_text)
            if fallback_parts and any(len(p.strip()) > 0 for p in fallback_parts):
                extracted = "\n".join(fallback_parts).strip()
                logger.info(f"PDF extraction successful (PyPDF2 fallback): {len(extracted)} chars")
                return extracted
        except Exception as e:
            logger.error(f"PyPDF2 fallback extraction failed: {e}")

        logger.warning("No text extracted from PDF")
        return None
    
    async def extract_sections(self, pdf_bytes: bytes) -> Dict[str, str]:
        """Extract structured sections from PDF resume."""
        text = await self.extract_text(pdf_bytes)
        if not text:
            return {}
        
        # Use existing section extraction
        from app.utils.text_cleaner import extract_sections
        return extract_sections(text)
    
    async def extract_metadata(self, pdf_bytes: bytes) -> Dict[str, any]:
        """Extract PDF metadata."""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            metadata = reader.metadata or {}
            return {
                "title": metadata.get('/Title', '') or '',
                "author": metadata.get('/Author', '') or '',
                "subject": metadata.get('/Subject', '') or '',
                "creator": metadata.get('/Creator', '') or '',
                "producer": metadata.get('/Producer', '') or '',
                "pages": len(reader.pages)
            }
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            return {"pages": 0}
