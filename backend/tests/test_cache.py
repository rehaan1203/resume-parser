import asyncio
from app.core.cache.cache_manager import CacheManager
async def main():
    cm = CacheManager()
    await cm.set("test", {"hello": "world"}, 3600)
    print("DONE")
asyncio.run(main())
