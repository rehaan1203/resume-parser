import asyncio
import json
from app.core.agents.orchestrator import Orchestrator

async def main():
    orchestrator = Orchestrator()
    request_data = {
        "resume": "Software engineer with 5 years of python experience, building APIs, web apps, and machine learning models.",
        "jd_text": "Senior python developer wanted with 5 years of experience in fastAPI, redis, postgresql, and AWS deployments.",
        "include_roadmap": True
    }
    
    async def progress(p, msg):
        print(f"[{p}%] {msg}")
        
    result = await orchestrator.process(request_data, progress_callback=progress)
    
    print("\n--- FINAL RESULT ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
