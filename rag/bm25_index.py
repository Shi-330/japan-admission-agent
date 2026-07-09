"""
Lightweight BM25 keyword index over document chunks.
Provides exact-match term scoring to complement pgvector semantic search.
"""
from typing import List, Tuple, Optional
from rank_bm25 import BM25Okapi

try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False


def _tokenize(text: str) -> List[str]:
    """Tokenize Chinese text: jieba word-level if available, else character-level."""
    if _HAS_JIEBA:
        tokens = list(jieba.cut(text))
    else:
        tokens = list(text)  # character-level fallback
    return [t.strip() for t in tokens if t.strip()]


class BM25Index:
    """Builds a BM25Okapi index over document chunks for keyword-aware search."""

    def __init__(self, documents: List[str] = None):
        """
        Args:
            documents: List of document text strings to index.
        """
        self._docs: List[str] = []
        self._tokenized: List[List[str]] = []
        self._index: Optional[BM25Okapi] = None
        if documents:
            self.fit(documents)

    def fit(self, documents: List[str]):
        """Build or rebuild the BM25 index from a list of document strings."""
        self._docs = list(documents)
        self._tokenized = [_tokenize(doc) for doc in self._docs]
        self._index = BM25Okapi(self._tokenized) if self._tokenized else None

    def search(self, query: str, k: int = 10) -> List[Tuple[int, float]]:
        """
        Search for top-k documents matching the query.
        Returns: list of (document_index, bm25_score) sorted by score descending.
        """
        if self._index is None or not self._tokenized:
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        scores = self._index.get_scores(query_tokens)
        # Rank: return top-k indices with scores
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in indexed[:k] if s > 0]

    @property
    def doc_count(self) -> int:
        return len(self._docs)

    @property
    def is_ready(self) -> bool:
        return self._index is not None
