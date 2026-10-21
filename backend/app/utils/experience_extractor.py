"""Extracts and calculates seniority deterministically."""
import re
import hashlib
from typing import Dict, Any, Optional
from app.utils.logger import logger
from app.utils.cache_manager import CacheManager
from app.ai.client import GenAIClient
from app.prompts.extraction_prompt import build_experience_extraction_prompt

async def extract_years_experience(text: str) -> int:
    """Extract years of experience from text using regex, fallback to LLM if needed."""
    if not text:
        return 0
        
    patterns = [
        r'(\d+)\+?\s*years?\s*of\s*experience',
        r'(\d+)\s*\+\s*years?\s*experience',
        r'experience[:\-]?\s*(\d+)',
        r'(\d+)\+?\s*yrs?\s*exp',
        r'minimum\s*of\s*(\d+)\s*years',
        r'(\d+)(?:\s*to\s*\d+)?\s*years',
    ]
    
    # We want to find the max years mentioned if multiple exist in resume,
    # or just the first matched requirement in JD. We'll collect all numbers.
    years_found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                years_found.append(int(match.group(1)))
            except ValueError:
                pass
                
    if years_found:
        return max(years_found)
    
    # --- LLM Fallback (Regex Failed) ---
    logger.warning("Regex extraction for years of experience failed. Falling back to LLM.")
    
    # Create cache key based on text hash
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_key = f"exp_extract:{text_hash}"
    
    cache_manager = CacheManager()
    
    # 1. Check cache first
    cached_years = await cache_manager.get(cache_key)
    if cached_years is not None:
        logger.info(f"Retrieved extracted years from cache: {cached_years}")
        return int(cached_years)
        
    # 2. Call LLM
    try:
        client = GenAIClient()
        prompt = build_experience_extraction_prompt(text)
        response = await client.generate_structured_content(
            prompt=prompt,
            output_schema={"years": 0}
        )
        years = response.get("years", 0)
        
        # 3. Cache the result
        await cache_manager.set(cache_key, years, ttl=86400) # Cache for 1 day
        logger.info(f"LLM successfully extracted {years} years of experience.")
        return years
    except Exception as e:
        logger.error(f"LLM fallback for experience extraction failed: {e}")
        return 0

