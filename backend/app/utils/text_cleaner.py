"""Text cleaning and normalization utilities."""
import re
from typing import Dict, List
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize
from app.utils.logger import logger

try:
    STOPWORDS = set(stopwords.words('english'))
except LookupError:
    # Fallback to empty if not downloaded yet
    STOPWORDS = set()

def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    - Remove extra whitespace
    - Remove special characters
    - Normalize unicode
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters (keep alphanumeric, common punctuation)
    text = re.sub(r'[^\w\s.,;:?!-]', ' ', text)
    
    # Remove extra whitespace again
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_sections(text: str) -> Dict[str, str]:
    """Extract common sections from resume or JD."""
    sections = {
        "skills": "",
        "experience": "",
        "education": "",
        "summary": ""
    }
    
    # Common section headers
    skill_patterns = [r'skills', r'technical skills', r'core competencies', r'expertise']
    exp_patterns = [r'experience', r'work experience', r'professional experience', r'employment']
    edu_patterns = [r'education', r'academic', r'qualifications']
    summary_patterns = [r'summary', r'profile', r'about me', r'objective']
    
    lines = text.split('\n')
    current_section = "summary"
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # Check for section headers
        if any(re.search(pattern, line_lower) for pattern in skill_patterns):
            current_section = "skills"
            continue
        elif any(re.search(pattern, line_lower) for pattern in exp_patterns):
            current_section = "experience"
            continue
        elif any(re.search(pattern, line_lower) for pattern in edu_patterns):
            current_section = "education"
            continue
        elif any(re.search(pattern, line_lower) for pattern in summary_patterns):
            current_section = "summary"
            continue
        
        # Add line to current section
        if line.strip():
            sections[current_section] += " " + line.strip()
    
    # Clean each section
    for key in sections:
        sections[key] = clean_text(sections[key])
    
    return sections

def remove_stopwords(text: str) -> str:
    """Remove English stopwords from text."""
    words = text.split()
    filtered_words = [w for w in words if w.lower() not in STOPWORDS]
    return ' '.join(filtered_words)

def extract_key_phrases(text: str, num_phrases: int = 10) -> List[str]:
    """Extract key phrases from text (simplified TF-IDF approach)."""
    from collections import Counter
    
    # Clean and tokenize
    text = clean_text(text.lower())
    words = text.split()
    
    # Remove stopwords
    words = [w for w in words if w not in STOPWORDS]
    
    # Count frequencies
    word_freq = Counter(words)
    
    # Extract most common phrases (n-grams)
    phrases = []
    for ngram_size in [2, 3, 1]:
        for i in range(len(words) - ngram_size + 1):
            phrase = ' '.join(words[i:i+ngram_size])
            if len(phrase.split()) > 1:
                phrases.append(phrase)
    
    # Count phrase frequencies
    phrase_freq = Counter(phrases)
    
    # Return top phrases
    return [p for p, _ in phrase_freq.most_common(num_phrases)]
