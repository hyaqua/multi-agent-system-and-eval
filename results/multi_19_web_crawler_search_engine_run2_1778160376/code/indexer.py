"""
Inverted index builder with TF-IDF computation and JSON persistence.
"""

import json
import math
import re
import threading
from stemmer import stem
from stopwords import STOPWORDS


def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, filtering non-alphanumeric."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return tokens


def normalize_tokens(tokens: list[str]) -> list[str]:
    """Apply stopword filtering and stemming."""
    result = []
    for token in tokens:
        if token in STOPWORDS:
            continue
        if len(token) < 2:
            continue
        result.append(stem(token))
    return result


class Indexer:
    """Thread-safe inverted index builder."""

    def __init__(self):
        self.lock = threading.Lock()
        # index: term -> {doc_id: tf}
        self.index: dict[str, dict[int, int]] = {}
        # doc_texts: doc_id -> original plain text (for snippets)
        self.doc_texts: dict[int, str] = {}
        # doc_meta: doc_id -> {url, title}
        self.doc_meta: dict[int, dict] = {}
        # doc_count
        self.doc_count = 0
        # finalized flag
        self.finalized = False
        # idf data (populated after finalize)
        self.idf: dict[str, float] = {}
        self.df: dict[str, int] = {}

    def add_document(
        self, doc_id: int, url: str, title: str, text: str
    ) -> None:
        """Tokenize, normalize, stem, filter and add to inverted index."""
        tokens = tokenize(text)
        normalized = normalize_tokens(tokens)

        # Count term frequencies in this doc
        tf_map: dict[str, int] = {}
        for tok in normalized:
            tf_map[tok] = tf_map.get(tok, 0) + 1

        with self.lock:
            for term, tf in tf_map.items():
                if term not in self.index:
                    self.index[term] = {}
                self.index[term][doc_id] = self.index[term].get(doc_id, 0) + tf

            self.doc_texts[doc_id] = text
            self.doc_meta[doc_id] = {"url": url, "title": title}
            self.doc_count = max(self.doc_count, doc_id)

    def finalize(self) -> None:
        """Compute IDF values after all documents are indexed."""
        with self.lock:
            N = self.doc_count
            if N == 0:
                self.finalized = True
                return

            for term, postings in self.index.items():
                df = len(postings)
                self.df[term] = df
                self.idf[term] = math.log(N / df) if df > 0 else 0.0

            self.finalized = True

    def save(self, path: str) -> None:
        """Persist the index to a JSON file."""
        if not self.finalized:
            self.finalize()

        with self.lock:
            data = {
                "N": self.doc_count,
                "docs": {
                    str(doc_id): {
                        "url": meta["url"],
                        "title": meta["title"],
                        "text": self.doc_texts.get(doc_id, ""),
                    }
                    for doc_id, meta in self.doc_meta.items()
                },
                "index": {
                    term: {
                        "postings": {str(doc_id): tf for doc_id, tf in postings.items()},
                        "df": self.df.get(term, 0),
                        "idf": self.idf.get(term, 0.0),
                    }
                    for term, postings in self.index.items()
                },
            }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self, path: str) -> None:
        """Load the index from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with self.lock:
            self.doc_count = data["N"]
            self.index = {}
            self.idf = {}
            self.df = {}
            self.doc_texts = {}
            self.doc_meta = {}

            for term, term_data in data["index"].items():
                postings = {
                    int(doc_id): tf
                    for doc_id, tf in term_data["postings"].items()
                }
                self.index[term] = postings
                self.df[term] = term_data["df"]
                self.idf[term] = term_data["idf"]

            for doc_id_str, doc_data in data["docs"].items():
                doc_id = int(doc_id_str)
                self.doc_texts[doc_id] = doc_data.get("text", "")
                self.doc_meta[doc_id] = {
                    "url": doc_data["url"],
                    "title": doc_data.get("title", ""),
                }

            self.finalized = True

    @property
    def total_terms(self) -> int:
        with self.lock:
            return len(self.index)
