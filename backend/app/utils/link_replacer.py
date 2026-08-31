"""Finds replacement links for broken ones using Tavily and YouTube APIs."""
import re
from typing import Optional, Dict, Any, List
from tavily import TavilyClient
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import settings
from app.utils.logger import logger

class LinkReplacer:
    """Finds replacement links for broken resources."""

    # Trusted YouTube channels for educational content
    TRUSTED_CHANNELS = [
        "TED-Ed",
        "CrashCourse",
        "MIT",
        "Stanford",
        "Harvard",
        "3Blue1Brown",
        "Kurzgesagt",
        "LegalEagle",
        "GoogleTechTalks",
        "IBMTechnology",
        "freeCodeCamp",
        "DataCamp",
        "Computerphile",
        "Code.org",
        "Khan Academy"
    ]

    def __init__(self):
        self.tavily_client = TavilyClient(api_key=settings.tavily_api_key)
        self.youtube_client = build('youtube', 'v3', developerKey=settings.youtube_api_key)
        self._replacement_cache = {}

    def _clean_topic(self, text: str) -> str:
        """Clean topic for better search results."""
        # Remove Day/Week prefixes
        cleaned = re.sub(r'^Day\s*\d+[:\-]\s*', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'^Week\s*\d+[:\-]\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Remove generic verbs for better search
        if len(cleaned.split()) > 3:
            cleaned = re.sub(r'^(Review|Study|Learn|Complete|Practice|Watch|Read)\s+', '', cleaned, flags=re.IGNORECASE)
        
        # Extract core topic (remove filler words)
        filler_words = ["of", "the", "a", "an", "for", "with", "on", "at", "from", "by", "in", "to"]
        words = cleaned.split()
        core_words = [w for w in words if w.lower() not in filler_words]
        
        # Return first 5-6 words as the core topic
        core_topic = " ".join(core_words[:6])
        
        return core_topic.strip() if core_topic else cleaned.strip()

    async def find_course_replacement(self, topic: str) -> Optional[str]:
        """Find a relevant free course using Tavily API."""
        try:
            cleaned_topic = self._clean_topic(topic)
            
            # Use a single comprehensive query to save time
            query = f"free {cleaned_topic} course OR {cleaned_topic} certification for beginners"
            
            import asyncio
            response = await asyncio.to_thread(self.tavily_client.search, query=query, max_results=8)
            
            urls_to_check = []
            for result in response.get("results", []):
                url = result.get("url")
                # Prefer known learning platforms
                if url and any(domain in url for domain in ["coursera.org", "edx.org", "udemy.com", "khanacademy.org"]):
                    urls_to_check.append(url)
            
            # Verify URLs in parallel
            if urls_to_check:
                working_urls = await self._verify_urls_parallel(urls_to_check)
                if working_urls:
                    logger.info(f"Found course: {working_urls[0]}")
                    return working_urls[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Course search failed: {e}")
            return None

    async def find_article_replacement(self, topic: str) -> Optional[str]:
        """Find a relevant article using Tavily API."""
        try:
            cleaned_topic = self._clean_topic(topic)
            
            # Search for articles
            query = f"{cleaned_topic} guide explained"
            import asyncio
            response = await asyncio.to_thread(self.tavily_client.search, query=query, max_results=5)
            
            authoritative_domains = [
                "nist.gov", "iapp.org", "edx.org", "coursera.org",
                "harvard.edu", "mit.edu", "stanford.edu",
                "github.com", "medium.com", "towardsdatascience.com"
            ]
            
            auth_urls_to_check = []
            fallback_urls_to_check = []
            
            for result in response.get("results", []):
                url = result.get("url")
                if not url:
                    continue
                if any(domain in url for domain in authoritative_domains):
                    auth_urls_to_check.append(url)
                else:
                    fallback_urls_to_check.append(url)
            
            # Check authoritative first in parallel
            if auth_urls_to_check:
                working_urls = await self._verify_urls_parallel(auth_urls_to_check)
                if working_urls:
                    logger.info(f"Found authoritative article: {working_urls[0]}")
                    return working_urls[0]
            
            # Check fallbacks in parallel
            if fallback_urls_to_check:
                working_urls = await self._verify_urls_parallel(fallback_urls_to_check)
                if working_urls:
                    logger.info(f"Found article: {working_urls[0]}")
                    return working_urls[0]
                    
            return None
            
        except Exception as e:
            logger.error(f"Article search failed: {e}")
            return None

    async def find_video_replacement(self, topic: str) -> Optional[str]:
        """Find a relevant YouTube video with preference to trusted channels."""
        try:
            cleaned_topic = self._clean_topic(topic)
            
            # Search YouTube
            import asyncio
            request = self.youtube_client.search().list(
                q=cleaned_topic,
                part="snippet",
                maxResults=5,
                type="video",
                videoDuration="medium"
            )
            response = await asyncio.to_thread(request.execute)
            
            trusted_urls_to_check = []
            fallback_urls_to_check = []
            
            for item in response.get("items", []):
                channel_title = item["snippet"]["channelTitle"]
                video_id = item["id"]["videoId"]
                url = f"https://www.youtube.com/watch?v={video_id}"
                
                is_trusted = any(trusted.lower() in channel_title.lower() for trusted in self.TRUSTED_CHANNELS)
                if is_trusted:
                    trusted_urls_to_check.append(url)
                else:
                    fallback_urls_to_check.append(url)
            
            # Check trusted first in parallel
            if trusted_urls_to_check:
                working_urls = await self._verify_urls_parallel(trusted_urls_to_check)
                if working_urls:
                    logger.info(f"Found trusted video: {working_urls[0]}")
                    return working_urls[0]
            
            # Check fallbacks in parallel
            if fallback_urls_to_check:
                working_urls = await self._verify_urls_parallel(fallback_urls_to_check)
                if working_urls:
                    logger.info(f"Found video: {working_urls[0]}")
                    return working_urls[0]
                    
            return None
            
        except HttpError as e:
            logger.error(f"YouTube search failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Video search failed: {e}")
            return None

    async def find_certification_replacement(self, topic: str) -> Optional[str]:
        """Find a working certification link using Tavily API."""
        try:
            cleaned_topic = self._clean_topic(topic)
            query = f"{cleaned_topic} certification"
            import asyncio
            response = await asyncio.to_thread(self.tavily_client.search, query=query, max_results=3)
            
            urls_to_check = [result.get("url") for result in response.get("results", []) if result.get("url")]
            
            if urls_to_check:
                working_urls = await self._verify_urls_parallel(urls_to_check)
                if working_urls:
                    logger.info(f"Found certification replacement: {working_urls[0]}")
                    return working_urls[0]
                    
            return None
            
        except Exception as e:
            logger.error(f"Certification search failed: {e}")
            return None

    async def _verify_urls_parallel(self, urls: List[str]) -> List[str]:
        """Verify multiple URLs in parallel and return the working ones."""
        import asyncio
        tasks = [self._quick_verify(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        working_urls = []
        for url, is_working in zip(urls, results):
            if isinstance(is_working, bool) and is_working:
                working_urls.append(url)
        return working_urls

    async def _quick_verify(self, url: str) -> bool:
        """Quickly verify a link using HEAD request (or GET for YouTube)."""
        try:
            import httpx
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            }
            async with httpx.AsyncClient(timeout=3.0, headers=headers) as client:
                if "youtube.com" in url or "youtu.be" in url:
                    test_url = url
                    if "/embed/" in url:
                        video_id = url.split("/embed/")[-1].split("?")[0]
                        test_url = f"https://www.youtube.com/watch?v={video_id}"
                    elif "youtu.be/" in url:
                        video_id = url.split("youtu.be/")[-1].split("?")[0]
                        test_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                    response = await client.get(test_url, follow_redirects=True)
                    text = response.text
                    if '"status":"ERROR"' in text or '"playabilityStatus":{"status":"ERROR"' in text or "This video isn't available anymore" in text:
                        return False
                    return 200 <= response.status_code < 400
                else:
                    response = await client.head(url, follow_redirects=True)
                    if response.status_code in [403, 405]:
                        response = await client.get(url, follow_redirects=True)
                    return 200 <= response.status_code < 400 or response.status_code in [401, 403]
        except:
            return False

    async def find_replacement(self, url: str, topic: str, link_type: str) -> Optional[str]:
        """Find replacement with tiered priority."""
        # Check if it's a major platform (don't replace if enabled)
        try:
            from app.config import settings
            if getattr(settings, "link_verification_skip_major_platforms", True):
                major_platforms = [
                    "coursera.org", "udemy.com", "edx.org", "youtube.com", "youtu.be",
                    "khanacademy.org", "pluralsight.com", "linkedin.com", "udacity.com", "futurelearn.com"
                ]
                if any(platform in url.lower() for platform in major_platforms):
                    logger.info(f"Skipping replacement for major platform: {url}")
                    return None
        except ImportError:
            pass

        cache_key = f"{topic}_{link_type}"
        if cache_key in self._replacement_cache:
            return self._replacement_cache[cache_key]
            
        result = None
        
        # Step 0: Certification (if explicitly asked for)
        if link_type == "certification":
            result = await self.find_certification_replacement(topic)
            
        if not result:
            # Step 1: Course
            result = await self.find_course_replacement(topic)
            
        if not result:
            # Step 2: Article
            result = await self.find_article_replacement(topic)
            
        if not result:
            # Step 3 & 4: YouTube (Trusted then Any)
            result = await self.find_video_replacement(topic)
                
        if result:
            self._replacement_cache[cache_key] = result
            logger.info(f"\n🔄 Replacing: {url}\n   Topic: \"{topic}\"\n   Type: {link_type}\n   Found: {result}\n")
        else:
            logger.warning(f"\n❌ Failed to find replacement for: {url}\n   Topic: \"{topic}\"\n   Type: {link_type}\n")
            
        return result
