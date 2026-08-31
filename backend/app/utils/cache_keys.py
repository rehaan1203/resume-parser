"""Cache key generation utilities."""
import hashlib
import json
from typing import Any, Dict, Optional
from app.config import settings

def generate_hash(data: Any) -> str:
    """Generate SHA-256 hash for cache key."""
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True)
    elif not isinstance(data, str):
        data = str(data)
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def get_embedding_key(text: str, model: Optional[str] = None) -> str:
    """Generate cache key for embedding."""
    model = model or settings.embedding_model
    text_hash = generate_hash(text)
    return f"emb:{model}:{text_hash}"

def get_resume_embedding_key(resume: str) -> str:
    """Generate cache key for resume embedding."""
    return get_embedding_key(resume, "resume")

def get_jd_embedding_key(jd: str) -> str:
    """Generate cache key for JD embedding."""
    return get_embedding_key(jd, "jd")

def get_analysis_key(resume: str, jd: str) -> str:
    """Generate cache key for analysis result."""
    combined = f"{resume}||{jd}"
    combined_hash = generate_hash(combined)
    return f"analysis:{combined_hash}"

def get_jd_url_key(url: str) -> str:
    """Generate cache key for JD from URL."""
    url_hash = generate_hash(url)
    return f"jd:url:{url_hash}"

def get_session_key(session_id: str) -> str:
    """Generate cache key for session data."""
    return f"session:{session_id}"

def get_stats_key() -> str:
    """Get cache statistics key."""
    return "cache:stats"

def get_index_key(index_name: str) -> str:
    """Get index key for search."""
    return f"idx:{index_name}"
