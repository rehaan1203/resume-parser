"""Orchestrates link validation and replacement."""
import re
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse
from app.utils.link_validator import LinkValidator
from app.utils.link_replacer import LinkReplacer
from app.utils.logger import logger

class LinkProcessor:
    """Processes all links in AI response."""

    def __init__(self):
        self.validator = LinkValidator()
        self.replacer = LinkReplacer()

    async def process_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Process all links in the AI response."""
        # Extract all links with their context
        links_with_context = self._extract_links_with_context(response)
        
        if not links_with_context:
            return response
        
        # Validate all links
        urls = [item["url"] for item in links_with_context]
        validation_results = await self.validator.validate_many(urls)
        
        # Process each link
        replacements = {}
        for item in links_with_context:
            url = item["url"]
            topic = item.get("topic", "")
            link_type = item.get("type", "resource")
            
            result = validation_results.get(url, {})
            
            if self.should_replace_link(result):
                # Link is broken, find replacement
                replacement = await self.replacer.find_replacement(url, topic, link_type)
                if replacement:
                    replacements[url] = replacement
                    logger.info(f"Replaced broken link: {url} → {replacement}")
                else:
                    # Remove the link entirely (we'll mark it for removal)
                    replacements[url] = None
                    logger.warning(f"No replacement found for: {url}")
            else:
                # Link is valid, keep it
                if result.get("final_url") and result["final_url"] != url:
                    # Link was redirected, update it
                    replacements[url] = result["final_url"]
                    logger.info(f"Updated redirect: {url} → {result['final_url']}")
        
        # Apply replacements to the response
        return self._apply_replacements(response, replacements)

    def should_replace_link(self, result: dict) -> bool:
        """
        Determine if a link should be replaced.
        Only replace if link is TRULY broken.
        """
        status = result.get("status_code")
        
        # Valid - keep
        if status in [200, 301, 302, 401, 403, 405]:
            return False
        
        # Temporary - retry then replace
        if status in [429, 500, 502, 503, 504]:
            # Log and retry (handled elsewhere)
            return True
        
        # Truly broken - replace
        if status in [404, 410]:
            return True
        
        # Connection errors, timeouts, or DNS issues (e.g. NXDOMAIN)
        if result.get("status") in ["timeout", "error"]:
            return True
            
        # Default to replacing if it's an unrecognized error without a valid status code
        if not status:
            return True
        
        return False

    def _extract_url_from_text(self, text: str) -> Optional[str]:
        """Extract a URL from a string if present."""
        # Avoid capturing trailing punctuation like parentheses or brackets in markdown
        match = re.search(r'(https?://[^\s\)"\'>\]]+)', text)
        return match.group(1) if match else None

    def _extract_links_with_context(self, obj: Any, path: str = "", current_topic: str = None) -> List[Dict[str, Any]]:
        """Extract all links with their surrounding context."""
        links = []
        
        if isinstance(obj, dict):
            # Try to find a topic at THIS dictionary level using the robust heuristic
            level_topic = self._extract_topic_from_context(obj, "")
            
            # If we found one, it overrides the parent's topic
            if level_topic:
                current_topic = level_topic
                
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if isinstance(value, str):
                    url = self._extract_url_from_text(value)
                    if url:
                        topic = self._extract_topic_from_context(obj, key, value, current_topic)
                        link_type = self._detect_link_type(url)
                        links.append({
                            "original_text": value,
                            "url": url,
                            "topic": topic,
                            "type": link_type,
                            "path": new_path
                        })
                elif isinstance(value, list):
                    for i, list_val in enumerate(value):
                        if isinstance(list_val, str):
                            url = self._extract_url_from_text(list_val)
                            if url:
                                topic = self._extract_topic_from_context(obj, key, list_val, current_topic)
                                link_type = self._detect_link_type(url)
                                links.append({
                                    "original_text": list_val,
                                    "url": url,
                                    "topic": topic,
                                    "type": link_type,
                                    "path": f"{new_path}[{i}]"
                                })
                        elif isinstance(list_val, (dict, list)):
                            links.extend(self._extract_links_with_context(list_val, f"{new_path}[{i}]", current_topic))
                elif isinstance(value, dict):
                    links.extend(self._extract_links_with_context(value, new_path, current_topic))
                    
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                links.extend(self._extract_links_with_context(item, new_path, current_topic))
                
        return links

    def _detect_link_type(self, url: str) -> str:
        """Detect type of link."""
        if "youtube.com" in url or "youtu.be" in url:
            return "video"
        elif "coursera.org" in url or "edx.org" in url or "udemy.com" in url:
            return "course"
        elif "certification" in url.lower() or "certify" in url.lower():
            return "certification"
        else:
            return "resource"

    def _extract_topic_from_context(self, context: Dict, current_key: str, text_value: str = "", inherited_topic: str = None) -> str:
        """Extract topic from surrounding context using heuristic detection."""
        topic = inherited_topic
        
        # 1. Try to extract from markdown link text if present (highest priority)
        if text_value:
            md_match = re.search(r'\[([^\]]+)\]\((https?://[^\s\)"\'>\]]+)\)', text_value)
            if md_match:
                topic = md_match.group(1)
                
        # 2. Look for action/description in same context using heuristics
        if isinstance(context, dict):
            # Keys to ignore (these are metadata, not topics)
            ignore_keys = {
                "url", "link", "type", "time", "estimated_time", "day", "week",
                "month", "phase", "duration", "status", "completed", "id"
            }
            
            # Keywords that suggest a key contains an action/task description
            action_keywords = ["act", "task", "desc", "goal", "foc", "skill", "top", "sub", "obj", "learn", "study", "review", "complete"]
            
            # Find a key that is clearly a task description
            found_heuristic_topic = None
            for key, value in context.items():
                if not isinstance(value, str):
                    continue
                if key.lower() in ignore_keys:
                    continue
                # Check if key contains action keywords OR value is descriptive (>=15 chars)
                if any(kw in key.lower() for kw in action_keywords) or len(value) >= 15:
                    cleaned = self._clean_topic(value)
                    if cleaned and len(cleaned) > 5:
                        found_heuristic_topic = cleaned
                        break
            
            if found_heuristic_topic:
                topic = found_heuristic_topic
            else:
                # Fallback to any string value that's not a URL
                for key, value in context.items():
                    if isinstance(value, str) and len(value) > 10:
                        if not value.startswith(("http://", "https://", "www.")):
                            cleaned = self._clean_topic(value)
                            if cleaned:
                                topic = cleaned
                                break
                    
        # 3. Fallback to key, but avoid generic keys
        if not topic:
            generic_keys = ["resources", "links", "urls", "roadmap", "items", "content", "video", "course"]
            if current_key and current_key.lower() not in generic_keys:
                topic = current_key
            else:
                # If we really have nothing, try to extract from URL path (if not youtube)
                url = self._extract_url_from_text(text_value) if text_value else None
                if url and "youtube.com" not in url and "youtu.be" not in url:
                    from urllib.parse import urlparse
                    path = urlparse(url).path
                    if path and path != "/":
                        topic = path.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")
                
                if not topic:
                    topic = "career development" # Last resort fallback
            
        # Clean the final topic to improve search relevance
        if isinstance(topic, str):
            topic = self._clean_topic(topic)
            
        return topic

    def _clean_topic(self, text: str) -> str:
        """Clean the topic text for better search results."""
        import re
        # Remove Day X: prefixes
        cleaned = re.sub(r'(?i)^Day\s*\d+[:\-]?\s*', '', text)
        cleaned = re.sub(r'(?i)^Week\s*\d+[:\-]?\s*', '', cleaned)
        # Remove trailing punctuation
        cleaned = cleaned.strip('.:;, ')
        # Remove "Review" or "Study" if they make the search too generic
        if len(cleaned.split()) > 3:
            cleaned = re.sub(r'(?i)^(Review|Study|Learn|Complete|Practice|Watch|Read)\s+', '', cleaned)
        return cleaned.strip()

    def _apply_replacements(self, obj: Any, replacements: Dict[str, str]) -> Any:
        """Apply replacements to the response object."""
        if isinstance(obj, dict):
            return {k: self._apply_replacements(v, replacements) for k, v in obj.items()}
        elif isinstance(obj, list):
            result_list = []
            for item in obj:
                replaced_item = self._apply_replacements(item, replacements)
                if replaced_item is not None and replaced_item != "":
                    result_list.append(replaced_item)
            return result_list
        elif isinstance(obj, str):
            url = self._extract_url_from_text(obj)
            if url:
                if url in replacements:
                    replacement = replacements[url]
                    if replacement is None:
                        return ""  # Remove if no replacement
                    
                    # If original was an embed URL, format the replacement as an embed URL too
                    if "/embed/" in url and "/watch?v=" in replacement:
                        video_id = replacement.split("v=")[-1].split("&")[0]
                        replacement = f"https://www.youtube.com/embed/{video_id}"
                        
                    # Only replace the URL portion, preserving surrounding markdown text, and enforce HTTPS
                    return obj.replace(url, replacement).replace("http://", "https://")
                return obj.replace("http://", "https://")
            return obj.replace("http://", "https://")
        else:
            return obj
