import asyncio
import uuid
import os
from dotenv import load_dotenv
load_dotenv()
from app.core.cache.cache_manager import CacheManager
from enum import Enum
from pydantic import BaseModel
class GapType(Enum):
    MINI = 'mini_upskill'
class Roadmap(BaseModel):
    title: str
async def main():
    cm = CacheManager()
    result = {
        'id': str(uuid.uuid4()),
        'overall_score': 100,
        'friction_points': [],
        'skill_gaps': [],
        'gap_strategies': [],
        'strengths': ['A', 'B', 'C'],
        'roadmap': [Roadmap(title='Quick Upskill')],
        'conditional_sections': {'roadmap': [Roadmap(title='Quick Upskill')]},
        'match_level': GapType.MINI,
    }
    print("Setting in cache...")
    success = await cm.set("test_key", result, 3600)
    print("Success:", success)
asyncio.run(main())
