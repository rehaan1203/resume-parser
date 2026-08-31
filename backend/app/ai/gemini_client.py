from google import genai
from google.genai import types

class GeminiClient:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def generate_text(self, prompt: str, model: str = "gemini-2.5-flash"):
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text
    
    def generate_embeddings(self, text: str, model: str | None = None):
        from app.config import settings
        model = model or settings.embedding_model
        response = self.client.models.embed_content(
            model=model,
            contents=text,
        )
        return response.embeddings
