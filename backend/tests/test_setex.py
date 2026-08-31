import asyncio
import redis.asyncio as redis
async def main():
    client = redis.Redis.from_url("redis://localhost:6379")
    try:
        await client.setex("foo", 10, "bar")
        print("setex works")
    except Exception as e:
        print(f"setex failed: {e}")
asyncio.run(main())
