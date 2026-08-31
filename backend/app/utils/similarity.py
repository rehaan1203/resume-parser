"""Similarity calculation utilities."""
import numpy as np
from typing import List, Dict, Tuple
from sklearn.metrics.pairwise import cosine_similarity
from app.utils.logger import logger

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2:
        return 0.0
    
    arr1 = np.array(vec1).reshape(1, -1)
    arr2 = np.array(vec2).reshape(1, -1)
    similarity = cosine_similarity(arr1, arr2)[0][0]
    return float(similarity)

def scale_similarity(similarity: float, baseline: float = 0.65) -> float:
    """
    Scale cosine similarity because modern dense embeddings (like Mistral/Gemini)
    are tightly clustered, meaning completely unrelated texts still have ~0.65 similarity.
    """
    if similarity <= baseline:
        return 0.0
    return min(1.0, (similarity - baseline) / (1.0 - baseline))

def calculate_match_score(embedding1: List[float], embedding2: List[float]) -> int:
    """
    Calculate overall match score (0-100).
    Higher = better match.
    """
    similarity = compute_cosine_similarity(embedding1, embedding2)
    # Scale from baseline to 100
    scaled = scale_similarity(similarity)
    return max(0, min(100, int(scaled * 100)))

def find_friction_points(
    resume_embeddings: Dict[str, List[float]],
    jd_embeddings: Dict[str, List[float]],
    threshold_scaled: float = 0.6
) -> List[Dict[str, any]]:
    """
    Find areas of high friction (low similarity).
    
    Returns:
        List of friction points with metadata
    """
    friction_points = []
    
    # Compare each resume section with JD sections
    for resume_section, resume_emb in resume_embeddings.items():
        for jd_section, jd_emb in jd_embeddings.items():
            if resume_emb and jd_emb:
                raw_similarity = compute_cosine_similarity(resume_emb, jd_emb)
                scaled_sim = scale_similarity(raw_similarity)
                
                if scaled_sim < threshold_scaled:
                    friction_points.append({
                        "resume_section": resume_section,
                        "jd_section": jd_section,
                        "similarity": scaled_sim,  # Store scaled for consistency
                        "severity": "critical" if scaled_sim < 0.3 else "warning" if scaled_sim < 0.5 else "info"
                    })
    
    # Sort by similarity (lowest first = highest friction)
    friction_points.sort(key=lambda x: x["similarity"])
    
    return friction_points

def calculate_section_similarities(
    resume_embeddings: Dict[str, List[float]],
    jd_embeddings: Dict[str, List[float]]
) -> Dict[str, float]:
    """Calculate similarities between all section pairs."""
    similarities = {}
    
    for r_section, r_emb in resume_embeddings.items():
        for j_section, j_emb in jd_embeddings.items():
            if r_emb and j_emb:
                key = f"{r_section}_vs_{j_section}"
                similarities[key] = compute_cosine_similarity(r_emb, j_emb)
    
    return similarities
