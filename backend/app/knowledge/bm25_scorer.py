"""BM25 Sparse Scorer & Reciprocal Rank Fusion (RRF) for RAG Knowledge Base.

Combines high-entropy exact acronym matching (e.g. 'DPDP', 'FHIR', 'BACnet', 'GAAP', 'SEBI')
with dense semantic vector embeddings to prevent rare statutory terms from being washed out.
"""
import math
import re
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter
from app.knowledge.models import VerifiedResource, ResourceSearchResult
from app.utils.logger import logger

class BM25Index:
    """In-memory BM25 sparse lexical retrieval engine."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_len: Dict[str, int] = {}
        self.avg_doc_len: float = 0.0
        self.doc_count: int = 0
        self.corpus: Dict[str, VerifiedResource] = {}
        self.doc_freqs: Dict[str, int] = Counter()
        self.term_freqs: Dict[str, Counter] = {}

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text preserving hyphenated terms and alphanumeric acronyms."""
        if not text:
            return []
        cleaned = text.lower()
        # Keep alphanumeric words and common acronym delimiters like hyphens (e.g. 'cert-in')
        tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", cleaned)
        return tokens

    def index_resources(self, resources: List[VerifiedResource]):
        """Index a collection of VerifiedResource items."""
        self.corpus = {r.id: r for r in resources}
        self.doc_count = len(resources)
        self.doc_len.clear()
        self.doc_freqs.clear()
        self.term_freqs.clear()

        total_tokens = 0
        for res in resources:
            doc_text = f"{res.title} {res.description} {' '.join(res.skills_covered)} {res.platform} {res.domain} {getattr(res, 'jurisdiction', 'GLOBAL')}"
            tokens = self.tokenize(doc_text)
            self.doc_len[res.id] = len(tokens)
            total_tokens += len(tokens)
            
            tf = Counter(tokens)
            self.term_freqs[res.id] = tf
            for term in tf.keys():
                self.doc_freqs[term] += 1

        self.avg_doc_len = (total_tokens / self.doc_count) if self.doc_count > 0 else 0.0
        logger.debug(f"BM25Index indexed {self.doc_count} documents (avg length: {self.avg_doc_len:.1f} tokens).")

    def _idf(self, term: str) -> float:
        """Calculate Robertson-Spärck Jones IDF with smoothing."""
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0.0
        # Standard BM25 IDF: ln((N - n + 0.5) / (n + 0.5) + 1)
        return math.log(((self.doc_count - df + 0.5) / (df + 0.5)) + 1.0)

    def score_document(self, query_tokens: List[str], doc_id: str) -> float:
        """Compute BM25 score for a specific document against query tokens."""
        if doc_id not in self.term_freqs or self.doc_count == 0:
            return 0.0
        
        score = 0.0
        d_len = self.doc_len.get(doc_id, 0)
        tf_dict = self.term_freqs[doc_id]

        for token in query_tokens:
            tf = tf_dict.get(token, 0)
            if tf == 0:
                continue
            idf = self._idf(token)
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (d_len / (self.avg_doc_len or 1.0)))
            score += idf * (numerator / denominator)

        return score

    def search(self, query: str, domain: Optional[str] = None, top_k: int = 10) -> List[Tuple[VerifiedResource, float]]:
        """Search indexed documents using BM25 scoring."""
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores: List[Tuple[VerifiedResource, float]] = []
        for doc_id, res in self.corpus.items():
            if domain and res.domain.lower() != domain.lower():
                continue
            s = self.score_document(query_tokens, doc_id)
            if s > 0.0:
                scores.append((res, s))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

class ReciprocalRankFusion:
    """Combines dense vector rank and BM25 sparse rank using Reciprocal Rank Fusion (RRF)."""

    def __init__(self, k: int = 60, weight_dense: float = 0.60, weight_sparse: float = 0.40):
        self.k = k
        self.weight_dense = weight_dense
        self.weight_sparse = weight_sparse

    def fuse(
        self,
        dense_results: List[Tuple[VerifiedResource, float]],
        sparse_results: List[Tuple[VerifiedResource, float]],
        top_k: int = 10
    ) -> List[ResourceSearchResult]:
        """
        Combine two ranked lists using standard Cormack RRF formula:
        RRF(d) = sum(w_m / (k + rank_m(d)))
        """
        all_resources: Dict[str, VerifiedResource] = {}
        rrf_scores: Dict[str, float] = {}

        # 1. Score dense rankings (1-indexed rank)
        for rank, (res, s_val) in enumerate(dense_results, start=1):
            if s_val <= 0.0:
                continue
            all_resources[res.id] = res
            rrf_scores[res.id] = rrf_scores.get(res.id, 0.0) + (self.weight_dense / (self.k + rank))

        # 2. Score sparse rankings (1-indexed rank)
        for rank, (res, s_val) in enumerate(sparse_results, start=1):
            if s_val <= 0.0:
                continue
            all_resources[res.id] = res
            rrf_scores[res.id] = rrf_scores.get(res.id, 0.0) + (self.weight_sparse / (self.k + rank))

        if not rrf_scores:
            return []

        # Normalize RRF scores to [0.0, 1.0]
        max_possible = (self.weight_dense / (self.k + 1)) + (self.weight_sparse / (self.k + 1))
        
        results: List[ResourceSearchResult] = []
        for doc_id, raw_rrf in rrf_scores.items():
            res = all_resources[doc_id]
            norm_score = round(min(1.0, raw_rrf / max_possible), 4)
            results.append(ResourceSearchResult(
                resource=res,
                score=norm_score,
                matched_skills=res.skills_covered
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

_GLOBAL_BM25: Optional[BM25Index] = None

def get_bm25_index() -> BM25Index:
    """Singleton getter for BM25Index."""
    global _GLOBAL_BM25
    if _GLOBAL_BM25 is None:
        _GLOBAL_BM25 = BM25Index()
    return _GLOBAL_BM25
