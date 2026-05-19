"""Inverted index builder with TF-IDF computation and JSON persistence."""

import json
import math
import re
from collections import defaultdict
from stemmer import stem
from stopwords import STOP_WORDS


class Indexer:
    """
    Builds an inverted index from crawled documents.
    Computes TF-IDF scores after crawling completes.
    Persists and loads index as JSON.
    """

    def __init__(self):
        # Document store: doc_id -> {url, title, text, raw_text}
        self.documents: dict[int, dict] = {}

        # Term frequency per document: term -> {doc_id: tf}
        self.term_doc_freq: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        # Document frequency: term -> number of docs containing term
        self.term_df: dict[str, int] = defaultdict(int)

        # Document length (for TF-IDF normalization): doc_id -> length
        self.doc_lengths: dict[int, float] = {}

        # TF-IDF vectors: doc_id -> {term: tfidf}
        self.tfidf_vectors: dict[int, dict[str, float]] = defaultdict(dict)

        # Total documents
        self.total_docs: int = 0

        # Next document ID
        self._next_id: int = 0

        # Lock for thread safety
        self._lock = __import__('threading').Lock()

    def add_document(self, url: str, title: str, text: str) -> int | None:
        """
        Add a document to the index.
        Tokenizes, normalizes, removes stopwords, stems, and updates
        term frequencies.

        Returns the document ID, or None if text is empty.
        """
        tokens = self._tokenize(text)

        if not tokens:
            return None

        with self._lock:
            doc_id = self._next_id
            self._next_id += 1
            self.total_docs += 1

            self.documents[doc_id] = {
                'url': url,
                'title': title or url,
                'text': text,
                'token_count': len(tokens),
            }

            # Count term frequencies in this document
            term_counts: dict[str, int] = defaultdict(int)
            for token in tokens:
                term_counts[token] += 1

            # Update inverted index and document frequency
            for term, count in term_counts.items():
                self.term_doc_freq[term][doc_id] = count
                self.term_df[term] += 1

            # Store raw term counts for TF-IDF computation later
            self.doc_lengths[doc_id] = float(len(tokens))

            return doc_id

    def compute_tfidf(self):
        """Compute TF-IDF scores for all documents after crawling."""
        with self._lock:
            N = float(self.total_docs) if self.total_docs > 0 else 1.0

            for term, doc_freqs in self.term_doc_freq.items():
                df = self.term_df.get(term, 1)
                idf = math.log(N / float(df))

                for doc_id, tf in doc_freqs.items():
                    tf_normalized = float(tf) / self.doc_lengths.get(doc_id, 1.0)
                    self.tfidf_vectors[doc_id][term] = tf_normalized * idf

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text: lowercase, remove punctuation, filter stopwords, stem.
        """
        # Lowercase
        text = text.lower()

        # Remove punctuation: keep only alphanumeric chars and whitespace
        text = re.sub(r'[^\w\s]', ' ', text)

        # Split on whitespace
        raw_tokens = text.split()

        # Filter and stem
        tokens = []
        for token in raw_tokens:
            # Remove short tokens and stopwords
            if len(token) <= 1:
                continue
            if token in STOP_WORDS:
                continue
            # Remove purely numeric tokens
            if token.isdigit():
                continue
            stemmed = stem(token)
            if len(stemmed) <= 1:
                continue
            tokens.append(stemmed)

        return tokens

    def save(self, filepath: str) -> bool:
        """Persist the index to a JSON file. Returns True on success, False on failure."""
        with self._lock:
            # Convert defaultdicts to regular dicts for JSON serialization
            data = {
                'documents': self.documents,
                'term_doc_freq': {term: dict(freqs)
                                  for term, freqs in self.term_doc_freq.items()},
                'term_df': dict(self.term_df),
                'doc_lengths': self.doc_lengths,
                'tfidf_vectors': dict(self.tfidf_vectors),
                'total_docs': self.total_docs,
                'next_id': self._next_id,
            }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            print(f'Warning: Could not save index to {filepath}: {e}',
                  file=__import__('sys').stderr)
            return False

    def load(self, filepath: str):
        """Load the index from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with self._lock:
            self.documents = data.get('documents', {})
            # Convert string keys back to int for documents
            self.documents = {
                int(k): v for k, v in self.documents.items()
            }

            self.term_doc_freq = defaultdict(lambda: defaultdict(int))
            for term, freqs in data.get('term_doc_freq', {}).items():
                for doc_id_str, count in freqs.items():
                    self.term_doc_freq[term][int(doc_id_str)] = count

            self.term_df = defaultdict(int, {
                k: v for k, v in data.get('term_df', {}).items()
            })

            self.doc_lengths = {
                int(k): v for k, v in data.get('doc_lengths', {}).items()
            }

            self.tfidf_vectors = defaultdict(dict)
            for doc_id_str, vec in data.get('tfidf_vectors', {}).items():
                self.tfidf_vectors[int(doc_id_str)] = vec

            self.total_docs = data.get('total_docs', 0)
            self._next_id = data.get('next_id', self.total_docs)

    def get_stats(self) -> dict:
        """Return statistics about the index."""
        with self._lock:
            unique_terms = len(self.term_df)
            return {
                'total_docs': self.total_docs,
                'unique_terms': unique_terms,
            }

    def get_term_freq(self, term: str, doc_id: int) -> int:
        """Get the raw term frequency for a term in a document."""
        with self._lock:
            return self.term_doc_freq.get(term, {}).get(doc_id, 0)

    def get_docs_with_term(self, term: str) -> set[int]:
        """Get all document IDs containing the given term."""
        with self._lock:
            return set(self.term_doc_freq.get(term, {}).keys())

    def get_tfidf(self, doc_id: int, term: str) -> float:
        """Get the TF-IDF score for a term in a document."""
        with self._lock:
            return self.tfidf_vectors.get(doc_id, {}).get(term, 0.0)

    def get_document(self, doc_id: int) -> dict | None:
        """Get a document by ID."""
        with self._lock:
            return self.documents.get(doc_id)
