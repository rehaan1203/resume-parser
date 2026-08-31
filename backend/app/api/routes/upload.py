"""File upload and parsing routes."""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.utils.pdf_parser import PDFParser
from app.utils.jd_extractor import JDExtractor
from app.utils.logger import logger

router = APIRouter()

@router.post(
    "/upload/resume",
    summary="Upload and parse resume PDF"
)
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file")
):
    """Upload a PDF resume and extract text."""
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    try:
        # Read file
        contents = await file.read()
        
        if len(contents) > 5 * 1024 * 1024:  # 5MB limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 5MB limit"
            )
        
        # Parse PDF
        parser = PDFParser()
        text = await parser.extract_text(contents)
        sections = await parser.extract_sections(contents)
        metadata = await parser.extract_metadata(contents)
        
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text from PDF"
            )
        
        return {
            "filename": file.filename,
            "text": text,
            "sections": sections,
            "metadata": metadata,
            "characters": len(text),
            "words": len(text.split()),
            "pages": metadata.get("pages", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.post(
    "/upload/jd",
    summary="Extract job description from URL"
)
async def extract_jd(
    url: str,
    parser: JDExtractor = Depends()
):
    """Extract job description from a URL."""
    try:
        result = await parser.extract(url)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract job description from URL"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"JD extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract JD: {str(e)}"
        )
