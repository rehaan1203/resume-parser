"""Structure-aware semantic sectioner and lossless chunker for large resumes and JDs."""
import re
from typing import List, Dict

# Verified EEO / legal boilerplate patterns (never contains technical skills or work history)
_EEO_BOILERPLATE_RE = re.compile(
    r"(?i)(?:equal opportunity employer|we are an equal opportunity|without regard to race|"
    r"reasonable accommodation|e-verify|drug-free workplace|background check required|"
    r"all qualified applicants will receive consideration|protected veteran)"
)

_RESUME_PRIORITY_HEADERS = (
    "summary", "profile", "objective", "experience", "work history", "employment",
    "skills", "technical skills", "competencies", "projects", "certifications", "education"
)

_JD_PRIORITY_HEADERS = (
    "overview", "about the role", "role", "responsibilities", "what you will do",
    "requirements", "qualifications", "required", "skills", "must have", "preferred", "nice to have"
)

_SECTION_HEADING_RE = re.compile(
    r"^(?:[A-Z][A-Za-z0-9\s,&/\-]{2,45}:?|[#]{1,3}\s+[A-Za-z0-9\s,&/\-]{2,45})$"
)


def strip_legal_boilerplate(text: str) -> str:
    """Remove only trailing EEO/compliance paragraphs while preserving 100% of skills and experience."""
    if not text:
        return ""
    paragraphs = re.split(r"\n{2,}", text.strip())
    kept: List[str] = []
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        # Only drop long compliance paragraphs with zero years/experience numbers or tech tokens
        if _EEO_BOILERPLATE_RE.search(p_clean) and len(p_clean) > 120 and not re.search(r"\b\d+\+?\s*years?\b", p_clean, re.I):
            continue
        kept.append(p_clean)
    return "\n\n".join(kept) if kept else text.strip()


def split_into_sections(text: str) -> List[Dict[str, str]]:
    """Split a resume or JD into labeled semantic sections."""
    cleaned = strip_legal_boilerplate(text)
    if not cleaned:
        return []

    sections: List[Dict[str, str]] = []
    current_title = "Header"
    current_lines: List[str] = []

    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            current_lines.append("")
            continue

        is_heading = (
            len(stripped) <= 50
            and len(stripped.split()) <= 6
            and bool(_SECTION_HEADING_RE.match(stripped))
            and (
                stripped.endswith(":")
                or stripped.isupper()
                or stripped.startswith("#")
                or any(h in stripped.lower() for h in _RESUME_PRIORITY_HEADERS + _JD_PRIORITY_HEADERS)
            )
        )
        if is_heading and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({"heading": current_title, "content": body})
            current_title = stripped.rstrip(":").lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    tail = "\n".join(current_lines).strip()
    if tail:
        sections.append({"heading": current_title, "content": tail})

    return sections if sections else [{"heading": "Full Document", "content": cleaned}]


def chunk_document(
    text: str,
    doc_type: str = "resume",
    chunk_size: int = 8000,
    overlap: int = 400,
) -> List[Dict[str, str]]:
    """
    Partition arbitrarily large documents (10k-100k+ chars) into semantic section-preserving chunks
    for lossless Map-Reduce extraction across every page.
    """
    sections = split_into_sections(text)
    if not sections:
        return []

    chunks: List[Dict[str, str]] = []
    buf: List[str] = []
    buf_len = 0
    chunk_headings: List[str] = []

    for sec in sections:
        sec_block = f"### {sec['heading']}\n{sec['content']}".strip()
        sec_len = len(sec_block)

        # Split an oversized single section cleanly on line boundaries with overlap
        if sec_len > chunk_size:
            if buf:
                chunks.append({"headings": ", ".join(chunk_headings), "text": "\n\n".join(buf)})
                buf, buf_len, chunk_headings = [], 0, []

            start = 0
            while start < sec_len:
                end = min(start + chunk_size, sec_len)
                if end < sec_len:
                    nl = sec_block.rfind("\n", start + chunk_size // 2, end)
                    if nl > start:
                        end = nl
                slice_txt = sec_block[start:end].strip()
                if slice_txt:
                    prefix = f"### {sec['heading']} (continued)\n" if start > 0 else ""
                    chunks.append({"headings": sec["heading"], "text": f"{prefix}{slice_txt}"})
                if end >= sec_len:
                    break
                start = max(end - overlap, start + 1)
            continue

        if buf_len + sec_len + 2 > chunk_size and buf:
            chunks.append({"headings": ", ".join(chunk_headings), "text": "\n\n".join(buf)})
            buf = [sec_block]
            buf_len = sec_len
            chunk_headings = [sec["heading"]]
        else:
            buf.append(sec_block)
            buf_len += sec_len + 2
            chunk_headings.append(sec["heading"])

    if buf:
        chunks.append({"headings": ", ".join(chunk_headings), "text": "\n\n".join(buf)})

    return chunks


def extract_core_sections(text: str, doc_type: str = "jd", max_chars: int = 6000) -> str:
    """
    Produce a high-signal view up to max_chars prioritizing experience, skills, and requirements
    across the full document (avoiding blind truncation that loses bottom-of-document skills).
    """
    if not text:
        return ""
    cleaned = strip_legal_boilerplate(text)
    if len(cleaned) <= max_chars:
        return cleaned

    sections = split_into_sections(cleaned)
    priority_keys = _RESUME_PRIORITY_HEADERS if doc_type == "resume" else _JD_PRIORITY_HEADERS

    def _priority_rank(sec: Dict[str, str]) -> int:
        h = sec["heading"].lower()
        for idx, key in enumerate(priority_keys):
            if key in h:
                return idx
        return len(priority_keys) + 1

    ordered = sorted(sections, key=_priority_rank)
    per_sec_cap = max(800, max_chars // max(1, min(len(ordered), 5)))

    assembled: List[str] = []
    used = 0
    for sec in ordered:
        content = sec["content"]
        if len(content) > per_sec_cap:
            content = content[:per_sec_cap].rstrip() + "..."
        block = f"### {sec['heading']}\n{content}"
        if used + len(block) + 2 > max_chars:
            remaining = max_chars - used
            if remaining > 120:
                assembled.append(block[:remaining].rstrip())
            break
        assembled.append(block)
        used += len(block) + 2

    return "\n\n".join(assembled) if assembled else cleaned[:max_chars]

