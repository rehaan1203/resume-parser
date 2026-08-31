"""Text chunking utilities for embedding generation."""
from typing import List, Dict
from app.utils.token_counter import estimate_tokens

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Input text
        chunk_size: Target chunk size in tokens
        overlap: Overlap between chunks in tokens
    
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    # Split into sentences
    import nltk
    
    sentences = nltk.sent_tokenize(text)
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for sent in sentences:
        sent_tokens = estimate_tokens(sent)
        
        if current_tokens + sent_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunks.append(' '.join(current_chunk))
            
            # Keep overlap (last sentences)
            overlap_sentences = []
            overlap_tokens = 0
            for s in reversed(current_chunk):
                s_tokens = estimate_tokens(s)
                if overlap_tokens + s_tokens <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens
                else:
                    break
            
            current_chunk = overlap_sentences
            current_tokens = overlap_tokens
        
        current_chunk.append(sent)
        current_tokens += sent_tokens
    
    # Add final chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def chunk_resume(resume: str, max_chunks: int = 10) -> List[Dict[str, str]]:
    """
    Chunk resume by sections with metadata.
    
    Returns:
        List of dicts: [{"section": "skills", "content": "...", "chunk_index": 0}]
    """
    from app.utils.text_cleaner import extract_sections
    
    sections = extract_sections(resume)
    chunks = []
    
    for section_name, content in sections.items():
        if content and len(content) > 100:
            # Split large sections into smaller chunks
            section_chunks = chunk_text(content, chunk_size=500, overlap=100)
            for i, chunk in enumerate(section_chunks):
                chunks.append({
                    "section": section_name,
                    "content": chunk,
                    "chunk_index": i
                })
    
    return chunks[:max_chunks]
