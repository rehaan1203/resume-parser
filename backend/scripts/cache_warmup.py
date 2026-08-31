"""Script to pre-warm cache with sample data."""
import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.cache.cache_manager import CacheManager
from app.core.cache.cache_keys import get_analysis_key
from app.services.cached_ai_service import CachedAIService
from app.utils.logger import logger
import json

async def warmup_cache():
    """Warm up cache with sample analyses."""
    logger.info("Starting cache warmup script")
    
    cache_manager = CacheManager()
    cached_service = CachedAIService()
    
    if not cache_manager.enabled:
        logger.warning("Cache is disabled, skipping warmup")
        return 0
    
    if not cache_manager.enabled:
        logger.warning("Cache is disabled, skipping warmup")
        return 0
    
    # Create sample analyses with different variations
    sample_pairs = [
        {
            "name": "python_developer",
            "resume": "Experienced Python developer with 5 years experience. Built APIs and microservices.",
            "jd": "Senior Python developer with Django experience. Need 5+ years Python."
        },
        {
            "name": "cloud_engineer",
            "resume": "Cloud engineer with AWS and Kubernetes expertise. Managed cloud infrastructure.",
            "jd": "Senior cloud engineer with AWS certification. Need Kubernetes experience."
        },
        {
            "name": "frontend_developer",
            "resume": "Frontend developer with React and TypeScript. Built responsive web apps.",
            "jd": "Senior frontend developer with React expertise. Need TypeScript experience."
        },
        {
            "name": "devops_engineer",
            "resume": "DevOps engineer with CI/CD and Docker expertise. Automating deployments.",
            "jd": "DevOps engineer with Jenkins and Docker. Need cloud experience."
        },
        {
            "name": "data_scientist",
            "resume": "Data scientist with Python and machine learning. Built predictive models.",
            "jd": "Senior data scientist with Python and ML. Need experience with TensorFlow."
        }
    ]
    
    warmed = 0
    
    for pair in sample_pairs:
        key = get_analysis_key(pair["resume"], pair["jd"])
        
        if not await cache_manager.exists(key):
            # Create a response structure
            response = {
                "id": f"warmup-{pair['name']}",
                "overall_score": 65 + (warmed * 5),
                "friction_points": [
                    {
                        "id": f"fp1-{pair['name']}",
                        "category": "skills",
                        "severity": "critical" if warmed % 2 == 0 else "warning",
                        "description": f"Missing key skills for {pair['name']} position",
                        "suggestion": f"Add relevant skills to your resume",
                        "related_to": "skills"
                    }
                ],
                "skill_gaps": ["Python", "Docker", "Kubernetes"][:warmed % 3 + 1],
                "strengths": ["Cloud expertise", "Leadership", "Communication"][:warmed % 3 + 1],
                "roadmap": [
                    {"week": 1, "day": 1, "action": "Learn fundamentals", "resources": ["https://example.com"], "completed": False},
                    {"week": 1, "day": 2, "action": "Practice daily", "resources": [], "completed": False}
                ],
                "timestamp": "2024-01-01T00:00:00Z",
                "warmup": True,
                "cache_metadata": {"hit": False, "warmup": True}
            }
            
            # Cache with 24-hour TTL
            await cache_manager.set(key, response, ttl=86400)
            warmed += 1
            logger.info(f"Warmed up cache for: {pair['name']}")
    
    logger.info(f"Cache warmup completed: {warmed} entries added")
    return warmed

if __name__ == "__main__":
    result = asyncio.run(warmup_cache())
    print(f"Warmed {result} cache entries")
