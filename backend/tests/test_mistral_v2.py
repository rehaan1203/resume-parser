import os
from dotenv import load_dotenv
from mistralai import Mistral
import asyncio

load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key)

async def test():
    try:
        print("Testing chat...")
        chat_response = await client.chat.complete_async(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print("Chat response received")
        
        print("Testing embeddings...")
        embed_response = await client.embeddings.create_async(
            model="mistral-embed",
            inputs=["Hello world", "Test batch"]
        )
        print("Embeddings shape:", len(embed_response.data[0].embedding))
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
