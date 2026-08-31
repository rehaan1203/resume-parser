"""PII scrubbing utilities - NO UI disclaimers needed."""
import re

def scrub_pii(text: str) -> str:
    """
    Remove personal identifiable information from text.
    Called internally before sending to external APIs.
    """
    if not text:
        return ""
        
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Remove phone numbers (US format)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
    
    # Remove LinkedIn URLs
    text = re.sub(r'linkedin\.com/in/[A-Za-z0-9-]+', '[LINKEDIN]', text)
    
    # Remove addresses (simplified)
    text = re.sub(r'\b\d{1,5}\s+[A-Za-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b', '[ADDRESS]', text)
    
    return text
