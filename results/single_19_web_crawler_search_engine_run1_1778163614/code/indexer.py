"""Inverted index with TF-IDF scoring and JSON persistence."""

import json
import math
import os
import threading
from typing import Optional


class Indexer:
    """Thread-safe inverted index with TF-IDF ranking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # doc_id (str) -> {url, title, text, length, term_freqs: {term: count}}
        self.documents: dict[str, dict] = {}
        # term -> {doc_id: term_frequency}
        self.inverted_index: dict[str, dict[str, int]] = {}
        self._next_doc_id = 0
        self._doc_count = 0
        self._crawl_duration: float = 0.0
        self._tfidf_computed = False
        # Cached idf values: term -> idf
        self._idf_cache: dict[str, float] = {}

    def add_document(self, url: str, title: str, text: str) -> None:
        """Add or update a document in the index (thread-safe)."""
        from utils import tokenize
        tokens = tokenize(text)

        # Build term frequency map
        tf_map: dict[str, int] = {}
        for t in tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        with self._lock:
            doc_id = str(self._next_doc_id)
            self._next_doc_id += 1

            self.documents[doc_id] = {
                'url': url,
                'title': title,
                'text': text,
                'length': len(tokens),
                'term_freqs': tf_map,
            }
            self._doc_count += 1

            # Update inverted index
            for term, count in tf_map.items():
                if term not in self.inverted_index:
                    self.inverted_index[term] = {}
                self.inverted_index[term][doc_id] = count

            self._tfidf_computed = False

    def compute_tfidf(self) -> None:
        """Pre-compute IDF values for all terms. Caller must hold lock or be single-threaded."""
        n = self._doc_count
        if n == 0:
            self._idf_cache = {}
            self._tfidf_computed = True
            return

        for term, postings in self.inverted_index.items():
            df = len(postings)  # document frequency
            idf = math.log((n + 1) / (df + 0.5)) + 1.0  # smoothed IDF (BM25-like)
            self._idf_cache[term] = idf

        self._tfidf_computed = True

    def _get_doc_tf(self, doc_id: str, term: str) -> float:
        """Get normalized term frequency for a term in a document."""
        doc = self.documents.get(doc_id)
        if doc is None:
            return 0.0
        raw_tf = doc['term_freqs'].get(term, 0)
        if doc['length'] == 0:
            return 0.0
        return raw_tf / doc['length']

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search the index and return ranked results."""
        from utils import tokenize, make_snippet

        query_tokens = tokenize(query)
        query_stems = set(query_tokens)

        if not query_stems:
            return []

        with self._lock:
            if not self._tfidf_computed:
                self.compute_tfidf()

            # Score each document
            scores: dict[str, float] = {}
            for term in query_stems:
                postings = self.inverted_index.get(term, {})
                idf = self._idf_cache.get(term, 0.0)
                for doc_id, tf in postings.items():
                    doc = self.documents.get(doc_id)
                    if doc is None:
                        continue
                    normalized_tf = tf / max(doc['length'], 1)
                    scores[doc_id] = scores.get(doc_id, 0.0) + normalized_tf * idf

            # Sort by score descending
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            results = []
            for doc_id, score in ranked[:limit]:
                doc = self.documents[doc_id]
                snippet = make_snippet(doc['text'], query_tokens)
                results.append({
                    'title': doc['title'] or doc['url'],
                    'url': doc['url'],
                    'score': round(score, 6),
                    'snippet': snippet,
                })

            return results

    def get_stats(self) -> dict:
        """Return index statistics."""
        with self._lock:
            # Estimate index size by serializing
            try:
                data = {
                    'documents': self.documents,
                    'inverted_index': self.inverted_index,
                    'doc_count': self._doc_count,
                }
                size_bytes = len(json.dumps(data, ensure_ascii=False))
            except Exception:
                size_bytes = 0

            return {
                'total_pages_crawled': self._doc_count,
                'total_unique_terms': len(self.inverted_index),
                'index_size_bytes': size_bytes,
                'crawl_duration_sec': round(self._crawl_duration, 3),
            }

    def set_crawl_duration(self, duration: float) -> None:
        self._crawl_duration = duration

    def save(self, path: str) -> None:
        """Persist the index to a JSON file."""
        with self._lock:
            self.compute_tfidf()
            data = {
                'documents': self.documents,
                'inverted_index': self.inverted_index,
                'next_doc_id': self._next_doc_id,
                'doc_count': self._doc_count,
                'crawl_duration': self._crawl_duration,
                'idf_cache': self._idf_cache,
            }
            json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json_str)

    def load(self, path: str) -> bool:
        """Load index from a JSON file. Returns True on success."""
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            with self._lock:
                self.documents = data.get('documents', {})
                self.inverted_index = data.get('inverted_index', {})
                self._next_doc_id = data.get('next_doc_id', len(self.documents))
                self._doc_count = data.get('doc_count', len(self.documents))
                self._crawl_duration = data.get('crawl_duration', 0.0)
                self._idf_cache = data.get('idf_cache', {})
                self._tfidf_computed = len(self._idf_cache) > 0

            return True
        except (json.JSONDecodeError, KeyError, IOError) as e:
            print(f'Error loading index: {e}')
            return False

    @property
    def doc_count(self) -> int:
        return self._doc_count
