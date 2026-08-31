"""Embedding generation and management service."""
import numpy as np
from typing import List, Dict, Optional
from app.ai.client import GenAIClient
from app.config import settings
from app.utils.logger import logger

class EmbeddingService:
    """Service for generating and managing text embeddings."""
    
    def __init__(self, client: GenAIClient):
        self.client = client
        if settings.embedding_model and settings.embedding_model.startswith("sentence-transformers/all-MiniLM-L6-v2"):
            self.embedding_dim = 384
        elif client.use_mistral:
            self.embedding_dim = 1024
        else:
            self.embedding_dim = 768
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return await self.client.generate_embedding(text)
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return await self.client.generate_embeddings(texts)
    
    def normalize_embedding(self, embedding: List[float]) -> List[float]:
        """Normalize embedding vector to unit length."""
        arr = np.array(embedding)
        norm = np.linalg.norm(arr)
        if norm > 0:
            return (arr / norm).tolist()
        return embedding
    
    async def embed_document(self, text: str) -> Dict[str, any]:
        """Embed a document and return metadata."""
        embedding = await self.generate_embedding(text)
        return {
            "embedding": self.normalize_embedding(embedding),
            "length": len(text),
            "tokens": len(text) // 4  # Rough estimate
        }
    
    async def embed_sections(self, sections: Dict[str, str]) -> Dict[str, List[float]]:
        """Generate embeddings for document sections."""
        embeddings = {}
        for section_name, content in sections.items():
            if content:
                embeddings[section_name] = await self.generate_embedding(content)
        return embeddings
