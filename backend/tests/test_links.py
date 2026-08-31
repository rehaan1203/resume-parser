import asyncio
import httpx

async def test_links():
    urls = [
        "https://www.youtube.com/watch?v=abc123def45", # fake video
        "https://kdnuggets.com/2020/08/data-anonymization-guide.html"
    ]
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for url in urls:
            print(f"Testing {url}")
            try:
                # HEAD request
                head_resp = await client.head(url)
                print(f"HEAD Status: {head_resp.status_code}")
                
                # GET request
                get_resp = await client.get(url)
                print(f"GET Status: {get_resp.status_code}")
                
                if "youtube" in url:
                    text = get_resp.text
                    print("YouTube specific checks:")
                    print(" 'Video unavailable' in text:", "Video unavailable" in text)
                    print(" 'This video isn\\'t available anymore' in text:", "This video isn't available anymore" in text)
                    print(" '\"status\":\"ERROR\"' in text:", '"status":"ERROR"' in text)
                    
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_links())
