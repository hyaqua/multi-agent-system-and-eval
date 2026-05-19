"""
Inverted index builder with TF-IDF scoring, stopword filtering,
text normalization, and JSON persistence.
"""

import json
import re
import math
import os
from collections import defaultdict
from crawler.stemmer import stem

# Common English stopwords
STOPWORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
    'which', 'this', 'that', 'these', 'those', 'then', 'just', 'so', 'than',
    'such', 'both', 'through', 'about', 'for', 'is', 'of', 'while', 'during',
    'to', 'from', 'in', 'on', 'at', 'by', 'with', 'without', 'its', 'it',
    'be', 'am', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
    'having', 'do', 'does', 'did', 'doing', 'would', 'could', 'should',
    'might', 'must', 'shall', 'will', 'can', 'may', 'not', 'no', 'nor',
    'into', 'up', 'out', 'down', 'off', 'over', 'under', 'again', 'further',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
    'every', 'few', 'more', 'most', 'other', 'some', 'only', 'own', 'same',
    'too', 'very', 'after', 'before', 'between', 'until', 'above', 'below',
    'any', 'he', 'she', 'they', 'them', 'their', 'his', 'her', 'my', 'your',
    'our', 'me', 'we', 'you', 'him', 'us', 'who', 'whom', 'i', 'the',
})


class Indexer:
    """Builds and queries an inverted index with TF-IDF scoring."""
    
    def __init__(self):
        # Inverted index: term -> {doc_url: term_frequency}
        self.index = defaultdict(dict)
        # Document metadata: doc_url -> {'title': ..., 'text': ..., 'length': ...}
        self.documents = {}
        # Total number of documents
        self.doc_count = 0
        # Total terms (unique)
        self.term_count = 0
        # Document frequencies: term -> number of docs containing it
        self.doc_frequencies = defaultdict(int)
        # Link domain tracking: domain -> count (how many times linked to)
        self.link_domains = defaultdict(int)
    
    def normalize_token(self, token):
        """Lowercase, strip punctuation from edges, filter stopwords."""
        token = token.lower().strip()
        # Remove leading/trailing punctuation
        token = re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', token)
        if not token or len(token) < 2:
            return None
        if token in STOPWORDS:
            return None
        if all(ch.isdigit() for ch in token):
            return None
        return token
    
    def tokenize(self, text):
        """Split text into normalized, stemmed tokens."""
        # Split on non-alphanumeric
        raw_tokens = re.split(r'[^a-zA-Z0-9]+', text)
        tokens = []
        for token in raw_tokens:
            norm = self.normalize_token(token)
            if norm:
                stemmed = stem(norm)
                if stemmed:
                    tokens.append(stemmed)
        return tokens
    
    def add_document(self, url, title, text):
        """Add a document to the index."""
        tokens = self.tokenize(text)
        
        # Count term frequencies in this document
        tf = defaultdict(int)
        for token in tokens:
            tf[token] += 1
        
        # Update inverted index
        for term, count in tf.items():
            self.index[term][url] = count
            self.doc_frequencies[term] += 1
        
        # Store document metadata
        self.documents[url] = {
            'title': title or url,
            'text': text,
            'length': len(tokens)
        }
        self.doc_count += 1
    
    def track_links(self, links):
        """Track outbound link domains for summary statistics."""
        from urllib.parse import urlparse
        for link in links:
            try:
                parsed = urlparse(link)
                domain = parsed.netloc.lower()
                if domain:
                    self.link_domains[domain] += 1
            except Exception:
                pass
    
    def compute_tfidf(self, query_terms):
        """Compute TF-IDF scores for documents matching query terms.
        Returns list of (url, score, title, snippet) sorted by score descending.
        """
        if not query_terms:
            return []
        
        # Collect candidate documents
        candidates = set()
        for term in query_terms:
            if term in self.index:
                candidates.update(self.index[term].keys())
        
        if not candidates:
            return []
        
        scores = {}
        for doc_url in candidates:
            score = 0.0
            doc_len = self.documents.get(doc_url, {}).get('length', 1)
            for term in query_terms:
                if term in self.index and doc_url in self.index[term]:
                    tf = self.index[term][doc_url] / max(doc_len, 1)
                    df = self.doc_frequencies.get(term, 1)
                    idf = math.log(self.doc_count / df) if df > 0 else 0
                    score += tf * idf
            if score > 0:
                scores[doc_url] = score
        
        # Sort by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for url, score in ranked:
            doc = self.documents[url]
            title = doc.get('title', url)
            snippet = self._generate_snippet(doc.get('text', ''), query_terms)
            results.append({
                'title': title,
                'url': url,
                'score': round(score, 4),
                'snippet': snippet
            })
        
        return results
    
    def _generate_snippet(self, text, query_terms):
        """Generate a text snippet around query term occurrences."""
        if not text or not query_terms:
            return text[:200] if text else ""
        
        text_lower = text.lower()
        best_pos = -1
        
        # Find first occurrence of any query term
        for term in query_terms:
            # Try to find the original form of the stemmed term
            pos = text_lower.find(term)
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos
        
        if best_pos == -1:
            return text[:200]
        
        # Extract window around the term
        window_size = 150
        start = max(0, best_pos - 60)
        end = min(len(text), best_pos + window_size)
        
        snippet = text[start:end]
        if start > 0:
            snippet = '...' + snippet
        if end < len(text):
            snippet = snippet + '...'
        
        return snippet.strip()
    
    def search(self, query_text, limit=None):
        """Search the index with a text query. Returns ranked results."""
        query_tokens = self.tokenize(query_text)
        results = self.compute_tfidf(query_tokens)
        
        if limit is not None and limit > 0:
            results = results[:limit]
        
        return results
    
    def save(self, filepath, crawl_duration=0.0):
        """Persist index to JSON file."""
        # Convert defaultdict to regular dict for JSON serialization
        data = {
            'index': {k: dict(v) for k, v in self.index.items()},
            'documents': self.documents,
            'doc_count': self.doc_count,
            'doc_frequencies': dict(self.doc_frequencies),
            'crawl_duration': crawl_duration,
            'link_domains': dict(self.link_domains),
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    
    def load(self, filepath):
        """Load index from JSON file. Returns crawl_duration if stored."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.index = defaultdict(dict)
        for term, postings in data.get('index', {}).items():
            self.index[term] = postings
        
        self.documents = data.get('documents', {})
        self.doc_count = data.get('doc_count', len(self.documents))
        self.doc_frequencies = defaultdict(int)
        for term, count in data.get('doc_frequencies', {}).items():
            self.doc_frequencies[term] = count
        
        self.link_domains = defaultdict(int)
        for domain, count in data.get('link_domains', {}).items():
            self.link_domains[domain] = count
        
        # Recalculate doc_count and doc_frequencies if missing
        if self.doc_count == 0:
            self.doc_count = len(self.documents)
        
        if not self.doc_frequencies:
            for term, postings in self.index.items():
                self.doc_frequencies[term] = len(postings)
        
        self.term_count = len(self.index)
        
        return data.get('crawl_duration', 0.0)
    
    def get_stats(self):
        """Get index statistics."""
        index_size = 0
        try:
            # Approximate size
            import sys
            index_size = sys.getsizeof(self.index) + sys.getsizeof(self.documents)
        except Exception:
            pass
        return {
            'total_pages': self.doc_count,
            'unique_terms': len(self.index),
            'index_size_bytes': index_size,
        }
    
    def get_top_linked_domains(self, n=10):
        """Get top N most linked domains from the crawled pages."""
        from collections import Counter
        
        # Use tracked link domains if available
        if self.link_domains:
            return Counter(self.link_domains).most_common(n)
        
        # Fallback: extract URLs from text content
        from urllib.parse import urlparse
        domain_counter = Counter()
        
        for url, doc in self.documents.items():
            text = doc.get('text', '')
            url_pattern = re.compile(r'https?://([^/\s"\'\]\)]+)')
            matches = url_pattern.findall(text)
            for match in matches:
                domain = match.split(':')[0]
                if domain:
                    domain_counter[domain] += 1
        
        return domain_counter.most_common(n)
