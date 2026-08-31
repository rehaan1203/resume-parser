import asyncio
import logging
from app.core.link_verification.link_processor import LinkProcessor

logging.basicConfig(level=logging.INFO)

async def test_pipeline():
    processor = LinkProcessor()
    
    # 1. Valid video
    # 2. Broken video
    payload = {
        "content": [
            "Valid video: https://www.youtube.com/watch?v=g34ZoiKJVG0",
            "Broken video: https://www.youtube.com/watch?v=invalid_id_12345",
            "Embed broken: https://www.youtube.com/embed/invalid_id_999",
            "Embed valid: https://www.youtube.com/embed/g34ZoiKJVG0"
        ]
    }
    
    print("BEFORE:", payload)
    
    processed = await processor.process_response(payload)
    
    print("AFTER:", processed)

if __name__ == "__main__":
    asyncio.run(test_pipeline())
