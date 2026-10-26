import os
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
client = MistralClient(api_key=api_key)

try:
    print("Testing chat...")
    chat_response = client.chat(
        model="mistral-small-latest",
        messages=[ChatMessage(role="user", content="Hello!")]
    )
    print("Chat:", chat_response.choices[0].message.content)

    print("Testing embeddings...")
    embed_response = client.embeddings(
        model="mistral-embed",
        input=["Hello world", "Test batch"]
    )
    print("Embeddings shape:", len(embed_response.data[0].embedding))
    print("Batch size returned:", len(embed_response.data))
except Exception as e:
    print("Error:", e)
