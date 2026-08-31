"""Tavily API for course search."""
from tavily import TavilyClient
from typing import List, Dict, Any
from app.config import settings
import asyncio

class WebSearch:
    """Search for courses using Tavily API."""

    def __init__(self):
        if settings.tavily_api_key:
            self.client = TavilyClient(api_key=settings.tavily_api_key)
        else:
            self.client = None

    async def search_courses(self, skill: str) -> List[Dict[str, Any]]:
        """Search for courses related to a skill."""
        if not self.client:
            return []
            
        try:
            query = f"best online course for {skill} for beginners"
            # Tavily client is synchronous, need to run in thread
            response = await asyncio.to_thread(
                self.client.search,
                query=query, 
                max_results=settings.tavily_search_limit
            )
            return [{
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")[:200]
            } for result in response.get("results", [])]
        except Exception:
            return []

    async def search_resources(self, skill_gaps: List[str]) -> Dict[str, List[Dict]]:
        """Search resources for multiple skill gaps."""
        results = {}
        for skill in skill_gaps[:3]:  # Limit to 3 skills
            results[skill] = await self.search_courses(skill)
        return results
