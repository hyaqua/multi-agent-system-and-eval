"""Search functionality: query processing, TF-IDF ranking, snippet generation."""

import re
from indexer import Indexer
from stemmer import stem
from stopwords import STOP_WORDS


class Searcher:
    """Processes search queries and returns ranked results with snippets."""

    def __init__(self, indexer: Indexer):
        self.indexer = indexer

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search the index for the given query.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            List of result dicts with keys: url, title, score, snippet.
        """
        query_terms = self._process_query(query)

        if not query_terms:
            return []

        # Find candidate documents (docs containing at least one query term)
        candidates: set[int] = set()
        for term in query_terms:
            docs = self.indexer.get_docs_with_term(term)
            candidates.update(docs)

        if not candidates:
            return []

        # Score each candidate
        scored: list[tuple[int, float]] = []
        for doc_id in candidates:
            score = self._compute_score(query_terms, doc_id)
            if score > 0:
                scored.append((doc_id, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for doc_id, score in scored[:limit]:
            doc = self.indexer.get_document(doc_id)
            if doc is None:
                continue

            snippet = self._generate_snippet(doc.get('text', ''), query_terms)

            results.append({
                'url': doc.get('url', ''),
                'title': doc.get('title', doc.get('url', '')),
                'score': round(score, 4),
                'snippet': snippet,
            })

        return results

    def _process_query(self, query: str) -> list[str]:
        """Normalize, tokenize, and stem a query string."""
        text = query.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        raw_tokens = text.split()

        terms = []
        for token in raw_tokens:
            if len(token) <= 1:
                continue
            if token in STOP_WORDS:
                continue
            if token.isdigit():
                continue
            stemmed = stem(token)
            if len(stemmed) <= 1:
                continue
            terms.append(stemmed)

        return terms

    def _compute_score(self, query_terms: list[str], doc_id: int) -> float:
        """
        Compute the TF-IDF score for a document given query terms.
        Uses sum of TF-IDF for each matching query term.
        """
        score = 0.0
        for term in query_terms:
            tfidf = self.indexer.get_tfidf(doc_id, term)
            score += tfidf
        return score

    def _generate_snippet(self, text: str, query_terms: list[str], window: int = 120) -> str:
        """
        Generate a text snippet around the first occurrence of a query term,
        with matched terms wrapped in <b> tags.
        """
        if not text:
            return ''

        lower_text = text.lower()

        # Find the first occurrence of any query term
        best_pos = -1

        for term in query_terms:
            # Try to find the term (unstemed) in the text
            # We search for the stem match approximately
            pos = lower_text.find(term)
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos

        if best_pos == -1:
            # No match found, return beginning of text
            snippet = text[:window * 2]
            if len(text) > window * 2:
                snippet += '...'
            return self._escape_html(snippet)

        # Extract window around the match
        start = max(0, best_pos - window // 2)
        end = min(len(text), best_pos + window // 2)

        # Adjust to word boundaries
        while start > 0 and text[start] != ' ':
            start -= 1
        while end < len(text) and text[end] != ' ':
            end += 1

        snippet = text[start:end]

        if start > 0:
            snippet = '...' + snippet
        if end < len(text):
            snippet = snippet + '...'

        # Bold the query terms in the snippet
        snippet = self._bold_terms(snippet, query_terms)

        return snippet

    def _bold_terms(self, text: str, query_terms: list[str]) -> str:
        """Wrap query term occurrences in <b> tags (case-insensitive)."""
        result = self._escape_html(text)

        for term in query_terms:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            result = pattern.sub(lambda m: f'<b>{m.group()}</b>', result)

        return result

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
        )
