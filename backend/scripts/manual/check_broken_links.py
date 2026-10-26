import httpx
import asyncio

async def main():
    valid_url = "https://www.youtube.com/watch?v=g34ZoiKJVG0"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(valid_url)
        text = response.text
        
        print("Status Code:", response.status_code)
        print("Is 'status\":\"OK\"' present?", '"status":"OK"' in text)
        print("Is 'playabilityStatus':{'status':'OK' present?", '"playabilityStatus":{"status":"OK"' in text)

asyncio.run(main())
