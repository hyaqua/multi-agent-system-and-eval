"""
Search engine: query processing, TF-IDF ranking, snippet generation.
"""

import math
import re
from indexer import Indexer, tokenize, normalize_tokens


class SearchEngine:
    """Loads a persisted index and performs TF-IDF search."""

    def __init__(self, indexer: Indexer):
        self.indexer = indexer

    def search(
        self, query: str, limit: int = 10
    ) -> list[dict]:
        """
        Process query, compute TF-IDF scores, rank documents,
        and return results with title, url, score, and snippet.
        """
        if not self.indexer.finalized:
            return []

        # Tokenize and normalize query
        query_tokens = tokenize(query)
        query_terms = normalize_tokens(query_tokens)

        if not query_terms:
            return []

        # Accumulate scores per document
        scores: dict[int, float] = {}
        for term in query_terms:
            if term not in self.indexer.index:
                continue

            idf = self.indexer.idf.get(term, 0.0)
            postings = self.indexer.index[term]

            for doc_id, tf in postings.items():
                # Use raw TF * IDF
                score = tf * idf
                scores[doc_id] = scores.get(doc_id, 0.0) + score

        if not scores:
            return []

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranked = ranked[:limit]

        results = []
        for doc_id, score in ranked:
            meta = self.indexer.doc_meta.get(doc_id, {})
            text = self.indexer.doc_texts.get(doc_id, "")
            snippet = self._generate_snippet(text, query_terms)

            results.append(
                {
                    "title": meta.get("title", ""),
                    "url": meta.get("url", ""),
                    "score": round(score, 4),
                    "snippet": snippet,
                }
            )

        return results

    def _generate_snippet(self, text: str, query_terms: list[str]) -> str:
        """
        Extract a ~150 character snippet around the first occurrence
        of any query term. Wrap all query term occurrences with <b> tags.
        """
        if not text or not query_terms:
            return ""

        text_lower = text.lower()

        # Find first occurrence of any query term
        best_pos = -1
        best_term = ""
        for term in query_terms:
            pos = text_lower.find(term.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos
                best_term = term

        # Extract window around the position
        window_size = 150
        if best_pos >= 0:
            start = max(0, best_pos - window_size // 2)
            end = min(len(text), best_pos + window_size // 2)

            # Adjust to word boundaries
            while start > 0 and text[start] != " ":
                start -= 1
            while end < len(text) and text[end] != " ":
                end += 1

            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
        else:
            snippet = text[:window_size].strip()
            if len(text) > window_size:
                snippet += "..."

        # Wrap query terms in <b> tags
        for term in query_terms:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            snippet = pattern.sub(r"<b>\g<0></b>", snippet)

        return snippet

    @property
    def total_pages(self) -> int:
        return self.indexer.doc_count

    @property
    def total_terms(self) -> int:
        return self.indexer.total_terms
