import asyncio
from app.core.link_verification.link_processor import LinkProcessor
from app.utils.logger import logger
import logging

logging.basicConfig(level=logging.INFO)

async def test_processor():
    processor = LinkProcessor()
    
    test_roadmap = {
        "content": [
            "Learn basics: [Watch here](https://www.youtube.com/watch?v=invalid_id_12345)",
            "Another video: https://youtu.be/missing_vid_999"
        ]
    }
    
    print("Before:", test_roadmap)
    
    links = processor._extract_links_with_context(test_roadmap)
    print("Links extracted:", links)
    
    urls = [item["url"] for item in links]
    validation_results = await processor.validator.validate_many(urls)
    print("Validation results:", validation_results)
    
    processed = await processor.process_response(test_roadmap)
    print("After:", processed)

if __name__ == "__main__":
    asyncio.run(test_processor())
