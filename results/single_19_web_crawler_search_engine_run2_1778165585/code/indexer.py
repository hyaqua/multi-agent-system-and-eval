"""Inverted index builder with TF-IDF scoring and JSON persistence.

Implements:
- Text normalization (lowercasing, punctuation removal, stopword filtering)
- Basic stemming
- Inverted index with term frequencies
- TF-IDF scoring
- JSON persistence
"""

import re
import json
import math
import os
import logging
from collections import defaultdict
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# English stopwords list (common words filtered out during indexing)
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "until",
    "while", "of", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "to",
    "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "s", "t", "can", "will", "just", "don", "should", "now", "d", "ll", "m",
    "o", "re", "ve", "y", "ain", "aren", "couldn", "didn", "doesn", "hadn",
    "hasn", "haven", "isn", "ma", "mightn", "mustn", "needn", "shan",
    "shouldn", "wasn", "weren", "won", "wouldn", "am", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "do",
    "does", "did", "doing", "would", "could", "should", "shall", "may",
    "might", "must", "can", "need", "dare", "ought", "used", "it", "its",
    "itself", "they", "them", "their", "theirs", "themselves", "what",
    "which", "who", "whom", "this", "that", "these", "those", "i", "me",
    "my", "myself", "we", "us", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "they", "them", "their", "theirs",
    "themselves", "anybody", "anyone", "anything", "everybody", "everyone",
    "everything", "nobody", "noone", "nothing", "somebody", "someone",
    "something", "each", "every", "all", "both", "few", "many", "much",
    "several", "some", "any", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very",
}


def tokenize(text: str) -> List[str]:
    """Normalize and tokenize text: lowercase, remove punctuation, split on whitespace."""
    # Lowercase
    text = text.lower()
    # Replace all non-alphanumeric characters with space
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Remove extra whitespace and split
    tokens = text.split()
    return tokens


def filter_stopwords(tokens: List[str]) -> List[str]:
    """Remove stopwords from token list."""
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def simple_stem(word: str) -> str:
    """A simple rule-based stemmer (simplified Porter-like).

    Handles common English suffixes: 'ing', 'ed', 'es', 's', 'ly', 'ment', 'tion', 'er', 'est'.
    """
    if len(word) <= 3:
        return word

    # Step 1: Long compound suffixes (strip these first)
    long_suffixes = [
        ("fulness", "ful"),
        ("ousness", "ous"),
        ("iveness", "ive"),
        ("tional", "tion"),
        ("ational", "ate"),
        ("alism", "al"),
        ("aliti", "al"),
        ("ation", "ate"),
        ("ements", "ement"),
        ("ities", "ity"),
        ("icing", "ice"),
        ("iness", "y"),
        ("ingly", "ing"),
        ("ments", "ment"),
        ("eness", "en"),
        ("ering", "er"),
        ("ested", "est"),
        ("izing", "ize"),
        ("ional", "ion"),
        ("ously", "ous"),
        ("ement", "e"),
        ("tion", "t"),
        ("ence", "ent"),
        ("ance", "ant"),
        ("ship", ""),
        ("less", ""),
        ("ness", ""),
        ("able", "abl"),
        ("ment", ""),
    ]
    for suffix, replacement in long_suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stemmed = word[: -len(suffix)] + replacement
            if len(stemmed) >= 2:
                return stemmed

    # Step 2: Handle -ing forms
    if word.endswith("ing") and len(word) > 5:
        stemmed = word[:-3]
        if len(stemmed) >= 2:
            fixed_double = False
            # Fix double consonant: "running" -> "runn" -> "run"
            if len(stemmed) >= 3 and stemmed[-1] == stemmed[-2] and stemmed[-1] not in "aeiou":
                stemmed = stemmed[:-1]
                fixed_double = True
            # Restore dropped 'e': "making" -> "mak" -> "make"
            # Only if we didn't just fix a double consonant and the result looks CVC
            if (
                not fixed_double
                and len(stemmed) >= 2
                and stemmed[-1] not in "aeiouyw"
                and stemmed[-2] in "aeiou"
            ):
                stemmed = stemmed + "e"
            return stemmed

    # Step 3: Handle -ed forms
    if word.endswith("ed") and len(word) > 4:
        stemmed = word[:-2]
        if len(stemmed) >= 2:
            fixed_double = False
            # Fix double consonant: "stopped" -> "stopp" -> "stop"
            if len(stemmed) >= 3 and stemmed[-1] == stemmed[-2] and stemmed[-1] not in "aeiou":
                stemmed = stemmed[:-1]
                fixed_double = True
            # Restore dropped 'e': "baked" -> "bak" -> "bake"
            if (
                not fixed_double
                and len(stemmed) >= 2
                and stemmed[-1] not in "aeiouyw"
                and stemmed[-2] in "aeiou"
            ):
                stemmed = stemmed + "e"
            return stemmed

    # Step 4: Plurals and -s
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ves") and len(word) > 4:
        return word[:-3] + "f"
    if word.endswith("es") and len(word) > 4:
        if word[-3] in "shxzo":
            return word[:-2]
        return word[:-1]
    if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        return word[:-1]

    # Step 5: -er, -est, -ly
    if word.endswith("est") and len(word) > 5:
        stemmed = word[:-3]
        if len(stemmed) >= 2:
            return stemmed
    if word.endswith("er") and len(word) > 4:
        stemmed = word[:-2]
        if len(stemmed) >= 2:
            return stemmed
    if word.endswith("ly") and len(word) > 4:
        return word[:-2]

    return word


def normalize_term(term: str) -> str:
    """Apply full normalization: stem and return cleaned term."""
    return simple_stem(term)


class Document:
    """Represents a crawled document."""

    def __init__(self, url: str, title: str, text: str, links: List[str]):
        self.url = url
        self.title = title or url
        self.text = text
        self.links = links
        self.term_frequencies: Dict[str, int] = {}
        self.doc_length = 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "links": self.links,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(
            url=d["url"],
            title=d.get("title", ""),
            text=d.get("text", ""),
            links=d.get("links", []),
        )


class InvertedIndex:
    """Inverted index with TF-IDF scoring."""

    def __init__(self):
        # term -> {doc_url: term_frequency}
        self.index: Dict[str, Dict[str, int]] = defaultdict(dict)
        # doc_url -> Document
        self.documents: Dict[str, Document] = {}
        # doc_url -> term_count
        self.doc_lengths: Dict[str, int] = {}
        # Total number of documents
        self.doc_count = 0
        # Total unique terms
        self.term_count = 0

    def add_document(self, doc: Document):
        """Index a document."""
        # Tokenize and normalize
        tokens = tokenize(doc.text)
        tokens = filter_stopwords(tokens)
        normalized_tokens = [normalize_term(t) for t in tokens]

        # Count term frequencies
        tf: Dict[str, int] = defaultdict(int)
        for term in normalized_tokens:
            tf[term] += 1

        doc.term_frequencies = dict(tf)
        doc.doc_length = len(normalized_tokens)

        self.documents[doc.url] = doc
        self.doc_lengths[doc.url] = len(normalized_tokens)
        self.doc_count += 1

        # Update inverted index
        for term, count in tf.items():
            self.index[term][doc.url] = count

        self.term_count = len(self.index)

    def get_term_frequency(self, term: str, doc_url: str) -> int:
        """Get term frequency in a document."""
        return self.index.get(term, {}).get(doc_url, 0)

    def get_document_frequency(self, term: str) -> int:
        """Get number of documents containing a term."""
        return len(self.index.get(term, {}))

    def compute_tfidf(self, term: str, doc_url: str) -> float:
        """Compute TF-IDF score for a term in a document."""
        tf = self.get_term_frequency(term, doc_url)
        if tf == 0:
            return 0.0

        df = self.get_document_frequency(term)
        if df == 0:
            return 0.0

        # TF component: log normalization
        tf_score = 1.0 + math.log(tf) if tf > 0 else 0.0

        # IDF component
        idf = math.log(self.doc_count / df) if self.doc_count > 0 else 0.0

        return tf_score * idf

    def search(self, query: str, limit: int = 20) -> List[dict]:
        """Search the index and return ranked results."""
        query_tokens = tokenize(query)
        query_tokens = filter_stopwords(query_tokens)
        query_terms = [normalize_term(t) for t in query_tokens]

        if not query_terms:
            return []

        # Score each document that matches any query term
        scores: Dict[str, float] = defaultdict(float)

        for term in query_terms:
            idf = math.log(self.doc_count / max(1, self.get_document_frequency(term)))
            for doc_url, tf in self.index.get(term, {}).items():
                tf_score = 1.0 + math.log(tf) if tf > 0 else 0.0
                scores[doc_url] += tf_score * idf

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for doc_url, score in ranked[:limit]:
            doc = self.documents.get(doc_url)
            if doc is None:
                continue

            snippet = self._generate_snippet(doc.text, query_terms, max_len=200)
            results.append({
                "title": doc.title or doc_url,
                "url": doc_url,
                "score": round(score, 4),
                "snippet": snippet,
            })

        return results

    def _generate_snippet(
        self, text: str, query_terms: List[str], max_len: int = 200
    ) -> str:
        """Generate a text snippet with query terms wrapped in bold tags."""
        # Find the best window around query terms
        text_lower = text.lower()
        best_pos = 0

        for term in query_terms:
            pos = text_lower.find(term)
            if pos != -1:
                # Start a bit before the term
                best_pos = max(0, pos - 60)
                break

        # Extract snippet window
        snippet = text[best_pos : best_pos + max_len]
        if best_pos > 0:
            snippet = "..." + snippet
        if best_pos + max_len < len(text):
            snippet = snippet + "..."

        # Wrap query terms in <b> tags
        for term in query_terms:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            snippet = pattern.sub(r"<b>\g<0></b>", snippet)

        return snippet

    def save(self, filepath: str):
        """Persist the index to a JSON file."""
        data = {
            "documents": {
                url: doc.to_dict() for url, doc in self.documents.items()
            },
            "doc_count": self.doc_count,
            "term_count": self.term_count,
        }

        # Save index separately for efficiency
        index_data = {
            "index": {term: dict(docs) for term, docs in self.index.items()},
            "doc_lengths": self.doc_lengths,
        }

        # We save both as a combined file
        combined = {"data": data, "index_data": index_data}

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False)

        logger.info(f"Index saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> "InvertedIndex":
        """Load the index from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            combined = json.load(f)

        instance = cls()

        data = combined.get("data", {})
        index_data = combined.get("index_data", {})

        # Restore documents
        for url, doc_dict in data.get("documents", {}).items():
            doc = Document.from_dict(doc_dict)
            instance.documents[url] = doc

        instance.doc_count = data.get("doc_count", 0)
        instance.term_count = data.get("term_count", 0)

        # Restore index
        raw_index = index_data.get("index", {})
        for term, doc_tfs in raw_index.items():
            instance.index[term] = dict(doc_tfs)

        instance.doc_lengths = index_data.get("doc_lengths", {})

        logger.info(
            f"Index loaded from {filepath}: "
            f"{instance.doc_count} docs, {instance.term_count} terms"
        )

        return instance
