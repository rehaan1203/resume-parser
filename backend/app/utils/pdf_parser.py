"""PDF parsing for resume extraction."""
import io
from typing import Optional, Dict, List
from PyPDF2 import PdfReader
import pdfplumber
from app.utils.logger import logger

class PDFParser:
    """Extract text and structure from PDF resumes."""
    
    async def extract_text(self, pdf_bytes: bytes) -> Optional[str]:
        """Extract text from PDF bytes."""
        try:
            # Try pdfplumber first (better for complex layouts)
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if text.strip():
                    logger.info(f"PDF extraction successful: {len(text)} chars")
                    return text
            
            # Fallback to PyPDF2
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            if text.strip():
                logger.info(f"PDF extraction successful (fallback): {len(text)} chars")
                return text
            
            logger.warning("No text extracted from PDF")
            return None
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
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
            metadata = reader.metadata
            return {
                "title": metadata.get('/Title', ''),
                "author": metadata.get('/Author', ''),
                "subject": metadata.get('/Subject', ''),
                "creator": metadata.get('/Creator', ''),
                "producer": metadata.get('/Producer', ''),
                "pages": len(reader.pages)
            }
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            return {}
