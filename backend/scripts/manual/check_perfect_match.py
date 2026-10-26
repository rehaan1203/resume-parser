import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient() as client:
        try:
            print("Sending request to analyze...")
            # Using same domain and exact same skills for 100%
            resp = await client.post("http://localhost:8000/api/v1/analyze", json={
                "resume": "Software Engineer with 10 years experience in Python, React, and Node.js. Used Jira for project management.",
                "jd_text": "We need a Software Engineer. Required skills: Python, React, Node.js."
            }, timeout=60.0)
            
            if resp.status_code == 200:
                data = resp.json()
                print("Score:", data.get("overall_score"))
                print("Gap Type:", data.get("match_level"))
                print("Has Roadmap:", data.get("conditional_sections", {}).get("roadmap") is not None)
                print("Roadmap Message:", data.get("conditional_sections", {}).get("roadmap_message"))
            else:
                print("Failed:", resp.status_code, resp.text)
        except Exception as e:
            print("Request failed:", e)

asyncio.run(main())
