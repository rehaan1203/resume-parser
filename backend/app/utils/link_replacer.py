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

    _SHARED_REPLACEMENT_CACHE: Dict[str, str] = {}
    _MAX_CACHE_SIZE = 512

    def __init__(self):
        self._tavily_client = None
        self._youtube_client = None
        self._replacement_cache = LinkReplacer._SHARED_REPLACEMENT_CACHE

    @property
    def tavily_client(self):
        if not getattr(settings, "tavily_api_key", None):
            return None
        if self._tavily_client is None:
            try:
                self._tavily_client = TavilyClient(api_key=settings.tavily_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Tavily client: {e}")
        return self._tavily_client

    @property
    def youtube_client(self):
        if not getattr(settings, "youtube_api_key", None):
            return None
        if self._youtube_client is None:
            try:
                self._youtube_client = build('youtube', 'v3', developerKey=settings.youtube_api_key, static_discovery=False)
            except Exception as e:
                logger.warning(f"Could not initialize YouTube client: {e}")
        return self._youtube_client

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

    def synthesize_canonical_search_url(self, topic: str, link_type: str = "resource") -> str:
        """
        Deterministic, zero-quota fallback URL synthesizer.
        When external search APIs (Tavily, YouTube Data API) are unavailable,
        exhausted, rate-limited, or return empty results, this synthesizes
        guaranteed-live, authoritative search/catalog endpoints with zero external calls.
        """
        import urllib.parse
        cleaned = self._clean_topic(topic)
        encoded = urllib.parse.quote_plus(cleaned)
        lower_topic = cleaned.lower()

        # 1. Video content
        if link_type == "video" or any(v in lower_topic for v in ["video", "watch", "youtube", "tutorial"]):
            return f"https://www.youtube.com/results?search_query={encoded}+tutorial"

        # 2. Certifications
        if link_type == "certification" or any(c in lower_topic for c in ["cert", "exam", "credential", "license"]):
            if any(cloud in lower_topic for cloud in ["azure", "microsoft"]):
                return f"https://learn.microsoft.com/en-us/credentials/browse/?terms={encoded}"
            if any(cloud in lower_topic for cloud in ["aws", "amazon"]):
                return f"https://aws.amazon.com/certification/certified-solutions-architect-associate/"
            return f"https://www.coursera.org/search?query={encoded}+certification"

        # 3. Domain-specific authoritative knowledge centers
        if any(tech in lower_topic for tech in ["azure", "microsoft", "powershell", "c#", ".net"]):
            return f"https://learn.microsoft.com/en-us/search/?terms={encoded}"
        if any(tech in lower_topic for tech in ["langgraph", "langchain", "multi-agent"]):
            return "https://langchain-ai.github.io/langgraph/"
        if any(tech in lower_topic for tech in ["aws", "amazon", "ec2", "s3", "lambda"]):
            return f"https://aws.amazon.com/search/?searchQuery={encoded}"
        if any(tech in lower_topic for tech in ["docker", "kubernetes", "k8s", "container"]):
            return f"https://docs.docker.com/search/?q={encoded}"
        if any(legal in lower_topic for legal in ["gdpr", "hipaa", "privacy", "compliance", "law", "legal"]):
            return f"https://www.coursera.org/search?query={encoded}+compliance"
        if any(health in lower_topic for health in ["clinical", "medical", "nursing", "healthcare", "fhir"]):
            return f"https://www.coursera.org/search?query={encoded}+healthcare"

        # 4. Canonical open learning platform fallback (Coursera)
        return f"https://www.coursera.org/search?query={encoded}"

    async def find_course_replacement(self, topic: str) -> Optional[str]:
        """Find a relevant free course using Tavily API, with zero-quota fallback."""
        if not self.tavily_client:
            return self.synthesize_canonical_search_url(topic, "course")
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
            
            # Fallback to deterministic canonical search
            canonical = self.synthesize_canonical_search_url(topic, "course")
            logger.info(f"Tavily returned no verified course, using canonical fallback: {canonical}")
            return canonical
            
        except Exception as e:
            logger.debug(f"Course search failed ({e}), using zero-quota fallback.")
            return self.synthesize_canonical_search_url(topic, "course")

    async def find_article_replacement(self, topic: str) -> Optional[str]:
        """Find a relevant article using Tavily API."""
        if not self.tavily_client:
            return self.synthesize_canonical_search_url(topic, "article")
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
                    
            # Fallback to canonical article/course search
            return self.synthesize_canonical_search_url(topic, "article")
            
        except Exception as e:
            logger.debug(f"Article search failed ({e}), using canonical fallback.")
            return self.synthesize_canonical_search_url(topic, "article")

    async def find_video_replacement(self, topic: str) -> Optional[str]:
        """Find a relevant YouTube video with preference to trusted channels, with zero-quota fallback."""
        if not self.youtube_client:
            return self.synthesize_canonical_search_url(topic, "video")
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
                    
            # Fallback to canonical YouTube educational search
            return self.synthesize_canonical_search_url(topic, "video")
            
        except HttpError as e:
            logger.debug(f"YouTube search quota/error ({e}), using zero-quota fallback.")
            return self.synthesize_canonical_search_url(topic, "video")
        except Exception as e:
            logger.debug(f"Video search failed ({e}), using zero-quota fallback.")
            return self.synthesize_canonical_search_url(topic, "video")

    async def find_certification_replacement(self, topic: str) -> Optional[str]:
        """Find a working certification link using Tavily API, with zero-quota fallback."""
        if not self.tavily_client:
            return self.synthesize_canonical_search_url(topic, "certification")
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
                    
            return self.synthesize_canonical_search_url(topic, "certification")
            
        except Exception as e:
            logger.debug(f"Certification search failed ({e}), using zero-quota fallback.")
            return self.synthesize_canonical_search_url(topic, "certification")

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
        # Check if it's a major platform (preserve original link if enabled)
        try:
            from app.config import settings
            if getattr(settings, "link_verification_skip_major_platforms", True):
                major_platforms = [
                    "coursera.org", "udemy.com", "edx.org", "youtube.com", "youtu.be",
                    "khanacademy.org", "pluralsight.com", "linkedin.com", "udacity.com", "futurelearn.com"
                ]
                if any(platform in url.lower() for platform in major_platforms):
                    logger.debug(f"Preserving original link for major platform: {url}")
                    return url
        except ImportError:
            pass

        cache_key = f"{topic}_{link_type}"
        if cache_key in self._replacement_cache:
            return self._replacement_cache[cache_key]
            
        result = None
        
        # Step 0: Certification (if explicitly asked for)
        if link_type == "certification":
            try:
                result = await self.find_certification_replacement(topic)
            except Exception as e:
                logger.debug(f"Certification lookup error: {e}")
            
        if not result:
            # Step 1: Course
            try:
                result = await self.find_course_replacement(topic)
            except Exception as e:
                logger.debug(f"Course lookup error: {e}")
            
        if not result:
            # Step 2: Article
            try:
                result = await self.find_article_replacement(topic)
            except Exception as e:
                logger.debug(f"Article lookup error: {e}")
            
        if not result:
            # Step 3 & 4: YouTube (Trusted then Any)
            try:
                result = await self.find_video_replacement(topic)
            except Exception as e:
                logger.debug(f"Video lookup error: {e}")

        # Fallback to zero-quota deterministic synthesizer if all external providers yielded nothing
        if not result:
            result = self.synthesize_canonical_search_url(topic, link_type)
            logger.info(f"Synthesized zero-quota canonical replacement for {url}: {result}")
                
        if len(self._replacement_cache) >= self._MAX_CACHE_SIZE:
            self._replacement_cache.clear()
        self._replacement_cache[cache_key] = result
        logger.info(f"\n🔄 Replacing: {url}\n   Topic: \"{topic}\"\n   Type: {link_type}\n   Found: {result}\n")
        return result
