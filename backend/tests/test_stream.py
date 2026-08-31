import httpx
import json
import asyncio

async def test_stream():
    url = "http://127.0.0.1:8000/api/v1/analyze/stream"
    payload = {
        "resume": "Software engineer with 5 years of python experience, building APIs, web apps, and machine learning models.",
        "jd_text": "Senior python developer wanted with 5 years of experience in fastAPI, redis, postgresql, and AWS deployments.",
        "include_roadmap": True
    }
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, timeout=60.0) as response:
            async for chunk in response.aiter_text():
                print(chunk)

if __name__ == "__main__":
    asyncio.run(test_stream())
