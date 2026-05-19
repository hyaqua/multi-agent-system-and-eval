"""Query processing, TF-IDF ranking, result snippet generation."""

from indexer import Indexer, tokenize, simple_stem, STOPWORDS
import re


class SearchEngine:
    """Search engine that loads an index and provides query ranking."""

    def __init__(self, indexer=None):
        self.indexer = indexer or Indexer()

    def load_index(self, filepath):
        """Load index from a JSON file."""
        self.indexer.load_from_file(filepath)

    def search(self, query, limit=10):
        """Search the index and return ranked results."""
        return self.indexer.search(query, limit)

    def get_stats(self, index_filepath=None):
        """Get index statistics."""
        stats = self.indexer.get_stats()
        if index_filepath:
            import os
            try:
                stats['index_size_bytes'] = os.path.getsize(index_filepath)
            except OSError:
                stats['index_size_bytes'] = 0
        return stats

    def get_top_linked_domains(self, n=10):
        """Get top linked domains."""
        return self.indexer.get_top_linked_domains(n)
