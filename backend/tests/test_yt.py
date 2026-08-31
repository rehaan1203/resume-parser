import asyncio
import httpx

async def test_yt():
    url = "https://www.youtube.com/watch?v=g34ZoiKJVG0"
    print(f"Testing {url}")
    
    # Use headers to bypass basic bot blocking if any
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        response = await client.get(url)
        print(f"Status: {response.status_code}")
        
        text = response.text
        print("Length of text:", len(text))
        print("Contains 'Video unavailable':", "Video unavailable" in text)
        print("Contains 'consent':", "consent" in text.lower())
        print("Contains 'status\":\"ERROR':", '"status":"ERROR"' in text)
        
        # Print a snippet to see what page it is
        if "<title>" in text:
            title_start = text.find("<title>")
            title_end = text.find("</title>")
            print("Title:", text[title_start:title_end+8])

if __name__ == "__main__":
    asyncio.run(test_yt())
