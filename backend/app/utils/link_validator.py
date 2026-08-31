"""Validates if a link is working using HEAD requests."""
import httpx
import asyncio
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse
from app.utils.logger import logger

class LinkValidator:
    """Validates links using HEAD requests."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers
        )

    async def validate(self, url: str) -> Dict[str, Any]:
        """Check if a link is working."""
        # Reject search query URLs (they return 200 but aren't specific resources)
        if "youtube.com/results" in url or "google.com/search" in url:
            return {
                "url": url,
                "status": "search_url",
                "status_code": 200,
                "final_url": None
            }

        try:
            # YouTube often returns 200 OK for unavailable videos, so we must GET and check HTML
            is_youtube = "youtube.com" in url or "youtu.be" in url
            if is_youtube:
                # Normalize to watch URL because embed pages have different HTML structures
                test_url = url
                if "/embed/" in url:
                    video_id = url.split("/embed/")[-1].split("?")[0]
                    test_url = f"https://www.youtube.com/watch?v={video_id}"
                elif "youtu.be/" in url:
                    video_id = url.split("youtu.be/")[-1].split("?")[0]
                    test_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                response = await self.client.get(test_url)
                if 200 <= response.status_code < 400:
                    text = response.text
                    # We MUST require the explicit OK status. If we hit a CAPTCHA or bot protection,
                    # this will be missing, and it's safer to treat the hallucinated video as broken 
                    # and replace it with a proven API result.
                    if '"playabilityStatus":{"status":"OK"' in text:
                        # We jump out of the youtube block to the success return below
                        pass
                    else:
                        return {
                            "url": url,
                            "status": "broken",
                            "status_code": 404,
                            "final_url": None
                        }
            else:
                response = await self.client.head(url)
                if response.status_code in [403, 405]:
                    response = await self.client.get(url)
            
            # Check if link is working (or blocked by bot protection)
            if 200 <= response.status_code < 400 or response.status_code in [401, 403]:
                return {
                    "url": url,
                    "status": "valid",
                    "status_code": response.status_code,
                    "final_url": str(response.url)
                }
            else:
                return {
                    "url": url,
                    "status": "broken",
                    "status_code": response.status_code,
                    "final_url": None
                }
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout while validating: {url}")
            return {"url": url, "status": "timeout", "status_code": None, "final_url": None}
            
        except httpx.HTTPStatusError as e:
            return {
                "url": url,
                "status": "error",
                "status_code": e.response.status_code,
                "final_url": None
            }
            
        except Exception as e:
            logger.error(f"Unexpected error validating {url}: {e}")
            return {"url": url, "status": "error", "status_code": None, "final_url": None}

    async def validate_many(self, urls: List[str], max_concurrent: int = 10) -> Dict[str, Dict[str, Any]]:
        """
        Validate multiple links in parallel with concurrency limit.
        
        Args:
            urls: List of URLs to validate
            max_concurrent: Maximum concurrent requests (default: 10, overridden by settings if available)
        """
        try:
            from app.config import settings
            max_concurrent = settings.link_verification_max_concurrent
        except ImportError:
            pass

        results = {}
        
        # Process in batches to avoid overwhelming servers
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i:i + max_concurrent]
            tasks = [self.validate(url) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error validating {url}: {result}")
                    results[url] = {"url": url, "status": "error", "status_code": None, "final_url": None}
                else:
                    results[url] = result
        
        return results
