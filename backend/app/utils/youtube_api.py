"""YouTube Data API v3 for video suggestions."""
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any
from app.config import settings
import asyncio

class YouTubeAPI:
    """Search for YouTube videos using Data API v3."""

    def __init__(self):
        self.api_key = settings.youtube_api_key
        if self.api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        else:
            self.youtube = None

    async def search_videos(self, skill: str, max_results: int = None) -> List[Dict[str, Any]]:
        """Search for YouTube videos related to a skill."""
        if not self.youtube:
            return []
            
        max_results = max_results or settings.youtube_search_limit
        try:
            request = self.youtube.search().list(
                q=f"{skill} tutorial for beginners",
                part="snippet",
                maxResults=max_results,
                type="video",
                videoDuration="medium"
            )
            
            # Execute synchronously in a thread
            response = await asyncio.to_thread(request.execute)

            videos = []
            for item in response.get("items", []):
                video_id = item["id"]["videoId"]
                videos.append({
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel": item["snippet"]["channelTitle"],
                    "description": item["snippet"]["description"][:200]
                })
            return videos
        except HttpError:
            return []
        except Exception:
            return []

    async def search_videos_for_gaps(self, skill_gaps: List[str]) -> Dict[str, List[Dict]]:
        """Search videos for multiple skill gaps."""
        results = {}
        for skill in skill_gaps[:3]:
            results[skill] = await self.search_videos(skill)
        return results
