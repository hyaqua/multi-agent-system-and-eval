"""Inverted index builder, simple stemmer, stopword filter, TF-IDF, persistence."""

import re
import json
import math
import os
import sys
import threading


# Common English stopwords
STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has',
    'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was',
    'were', 'will', 'with', 'this', 'but', 'they', 'have', 'had', 'not',
    'or', 'nor', 'so', 'if', 'then', 'than', 'too', 'very', 'can', 'do',
    'does', 'did', 'about', 'up', 'out', 'all', 'just', 'now', 'been',
    'only', 'also', 'into', 'over', 'some', 'would', 'could', 'should',
    'may', 'might', 'must', 'shall', 'after', 'before', 'between',
    'through', 'during', 'under', 'again', 'further', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'which', 'who', 'whom',
    'what', 'both', 'each', 'every', 'more', 'most', 'other', 'own',
    'same', 'such', 'these', 'those', 'me', 'my', 'myself', 'we', 'our',
    'ours', 'ourselves', 'your', 'yours', 'yourself', 'yourselves',
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
    'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
    'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
    'had', 'having', 'do', 'does', 'did', 'doing', 'would', 'could',
    'should', 'might', 'must', 'can', 'will', 'shall', 'no', 'not',
    'nor', 'any', 'all', 'both', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
    'i', 'you', 'your', 'yours', 'me', 'my', 'mine', 'we', 'us', 'our', 'ours',
    'he', 'him', 'his', 'she', 'her', 'hers', 'it', 'its', 'they', 'them',
    'their', 'theirs', 'this', 'that', 'these', 'those', 'here', 'there',
    'who', 'whom', 'whose', 'which', 'what', 'when', 'where', 'why', 'how',
    'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'so', 'yet',
    'at', 'by', 'in', 'into', 'of', 'on', 'to', 'with', 'as', 'from',
    'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'here', 'there', 'all', 'both', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'not', 'only', 'own', 'same',
    'than', 'too', 'very', 'just', 'because', 'about', 'between',
    'through', 'during', 'before', 'after', 'above', 'below', 'while',
    'against', 'until'
}


def simple_stem(word):
    """A simple suffix-stripping stemmer (Porter-like but simplified)."""
    if len(word) <= 2:
        return word

    # Remove trailing 's (possessive)
    word = re.sub(r"'s$", "", word)

    # Step 1a: plurals
    if word.endswith('sses'):
        word = word[:-2]  # sses -> ss
    elif word.endswith('ies'):
        word = word[:-3] + 'y'  # ies -> y
    elif word.endswith('ss'):
        pass  # keep ss
    elif word.endswith('s') and len(word) > 2:
        word = word[:-1]  # s -> ''

    # Step 2: -ed, -ing
    if word.endswith('eed') and len(word) > 4:
        # eed -> ee if preceded by non-vowel
        if word[-4] not in 'aeiou':
            word = word[:-1]  # eed -> ee
    elif word.endswith('ed') and len(word) > 3:
        stem = word[:-2]
        if any(c in 'aeiou' for c in stem):
            word = stem
            if word.endswith('at') or word.endswith('bl') or word.endswith('iz'):
                word += 'e'
            elif len(word) >= 2 and word[-1] == word[-2] and word[-1] not in 'aeiouls':
                word = word[:-1]
    elif word.endswith('ing') and len(word) > 4:
        stem = word[:-3]
        if any(c in 'aeiou' for c in stem):
            word = stem
            if word.endswith('at') or word.endswith('bl') or word.endswith('iz'):
                word += 'e'
            elif len(word) >= 2 and word[-1] == word[-2] and word[-1] not in 'aeiouls':
                word = word[:-1]

    # Step 3: -ly, -y
    if word.endswith('ly') and len(word) > 3:
        word = word[:-2]
    elif word.endswith('y') and len(word) > 3:
        word = word[:-1] + 'i'

    return word


def tokenize(text):
    """Tokenize text: lowercase, split on word boundaries, filter."""
    if not text:
        return []
    # Get all word characters (letters and apostrophes for contractions)
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    result = []
    for token in tokens:
        token = token.strip("'")
        if (len(token) > 1 and
                token not in STOPWORDS and
                not token.isdigit()):
            stemmed = simple_stem(token)
            if len(stemmed) > 1:
                result.append(stemmed)
    return result


class Indexer:
    """Builds the inverted index and manages persistence."""

    def __init__(self):
        self._lock = threading.Lock()
        self.documents = []  # list of {url, title, text, outlinks}
        self.inverted_index = {}  # term -> {doc_id: tf}
        self.doc_count = 0
        self.idf_values = {}  # term -> idf
        self.built = False

    def add_document(self, doc):
        """Add a document to the index (thread-safe)."""
        with self._lock:
            doc_id = len(self.documents)
            self.documents.append(doc)
            return doc_id

    def add_documents_batch(self, docs):
        """Add multiple documents."""
        for doc in docs:
            self.add_document(doc)

    def build_index(self):
        """Build the inverted index from all stored documents."""
        with self._lock:
            self.inverted_index = {}
            self.doc_count = len(self.documents)

            for doc_id, doc in enumerate(self.documents):
                text = doc.get('text', '') + ' ' + doc.get('title', '')
                tokens = tokenize(text)

                # Count term frequencies in this document
                tf_counts = {}
                for token in tokens:
                    tf_counts[token] = tf_counts.get(token, 0) + 1

                # Update inverted index
                for term, tf in tf_counts.items():
                    if term not in self.inverted_index:
                        self.inverted_index[term] = {}
                    self.inverted_index[term][doc_id] = tf

            # Compute IDF values
            N = self.doc_count
            self.idf_values = {}
            for term, doc_dict in self.inverted_index.items():
                df = len(doc_dict)
                self.idf_values[term] = math.log(1 + N / (1 + df))

            self.built = True
            print(f"\nIndex built: {self.doc_count} documents, "
                  f"{len(self.inverted_index)} unique terms.")

    def get_tfidf(self, term, doc_id):
        """Compute TF-IDF for a term in a document."""
        if not self.built or term not in self.inverted_index:
            return 0.0
        if doc_id not in self.inverted_index[term]:
            return 0.0
        tf = self.inverted_index[term][doc_id]
        idf = self.idf_values.get(term, 0.0)
        return tf * idf

    def search(self, query_text, limit=10):
        """Search the index with a query string, return ranked results."""
        if not self.built:
            return []

        query_tokens = tokenize(query_text)
        if not query_tokens:
            return []

        # Find matching documents and compute scores
        scores = {}  # doc_id -> score
        for token in query_tokens:
            if token in self.inverted_index:
                idf = self.idf_values.get(token, 0.0)
                for doc_id, tf in self.inverted_index[token].items():
                    scores[doc_id] = scores.get(doc_id, 0.0) + tf * idf

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Build results with snippets
        results = []
        for doc_id, score in ranked[:limit]:
            doc = self.documents[doc_id]
            snippet = self._generate_snippet(doc.get('text', ''), query_tokens)
            results.append({
                'title': doc.get('title', doc.get('url', 'Untitled')),
                'url': doc.get('url', ''),
                'score': round(score, 4),
                'snippet': snippet
            })

        return results

    def _generate_snippet(self, text, query_terms):
        """Generate a text snippet with query terms wrapped in <b> tags."""
        if not text:
            return ''

        text_lower = text.lower()
        snippet_len = 150

        # Find the first occurrence of any query term
        best_pos = -1
        for term in query_terms:
            pos = text_lower.find(term.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos

        if best_pos == -1:
            # No term found, return start of text
            snippet = text[:snippet_len] + ('...' if len(text) > snippet_len else '')
        else:
            start = max(0, best_pos - 60)
            end = min(len(text), best_pos + snippet_len)
            snippet = text[start:end]
            if start > 0:
                snippet = '...' + snippet
            if end < len(text):
                snippet = snippet + '...'

        # Wrap query terms in <b> tags
        for term in query_terms:
            # Case-insensitive replacement with <b>
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            snippet = pattern.sub(r'<b>\g<0></b>', snippet)

        return snippet

    def save_to_file(self, filepath):
        """Persist the index to a JSON file."""
        with self._lock:
            # Convert inverted index to serializable format
            serializable_terms = {}
            for term, doc_dict in self.inverted_index.items():
                # Convert doc_id keys to strings for JSON
                serializable_terms[term] = {
                    'df': len(doc_dict),
                    'docs': {str(k): v for k, v in doc_dict.items()}
                }

            data = {
                'doc_count': self.doc_count,
                'terms': serializable_terms,
                'docs': {str(i): {
                    'url': doc.get('url', ''),
                    'title': doc.get('title', ''),
                    'text_snippet': doc.get('text', '')[:200]
                } for i, doc in enumerate(self.documents)},
                'idf': self.idf_values
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)

            file_size = os.path.getsize(filepath)
            print(f"Index saved to {filepath} ({file_size} bytes)")

    def load_from_file(self, filepath):
        """Load index from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with self._lock:
            self.doc_count = data['doc_count']
            self.idf_values = data.get('idf', {})

            # Reconstruct inverted index
            self.inverted_index = {}
            for term, term_data in data['terms'].items():
                self.inverted_index[term] = {
                    int(k): v for k, v in term_data['docs'].items()
                }

            # Reconstruct documents
            self.documents = []
            for i in range(self.doc_count):
                doc_data = data['docs'].get(str(i), {})
                self.documents.append({
                    'url': doc_data.get('url', ''),
                    'title': doc_data.get('title', ''),
                    'text': doc_data.get('text_snippet', ''),
                })

            self.built = True
            print(f"Index loaded from {filepath}: {self.doc_count} documents, "
                  f"{len(self.inverted_index)} unique terms.")

    def get_stats(self):
        """Return statistics about the index."""
        if not self.built:
            return {
                'pages_crawled': 0,
                'unique_terms': 0,
                'index_size_bytes': 0,
                'crawl_duration_seconds': 0
            }

        return {
            'pages_crawled': self.doc_count,
            'unique_terms': len(self.inverted_index),
            'index_size_bytes': 0,  # Will be set by caller if needed
            'crawl_duration_seconds': 0
        }

    def get_top_linked_domains(self, top_n=10):
        """Get the top N most linked domains from the crawl."""
        from url_utils import get_domain
        from collections import Counter

        domain_counts = Counter()
        for doc in self.documents:
            outlinks = doc.get('outlinks', [])
            if isinstance(outlinks, list):
                for link in outlinks:
                    domain = get_domain(link)
                    if domain:
                        domain_counts[domain] += 1

        return domain_counts.most_common(top_n)
