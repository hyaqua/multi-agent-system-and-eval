"""Utility functions for progress reporting, summary, and logging."""

import os
from indexer import Indexer
from crawl_manager import CrawlManager


def print_summary(
    crawl_manager: CrawlManager,
    indexer: Indexer,
    elapsed: float,
    index_path: str = '',
):
    """Print a summary report after crawling completes."""
    print('\n' + '=' * 60)
    print('  CRAWL SUMMARY')
    print('=' * 60)

    stats = indexer.get_stats()

    print(f'  Total pages crawled:      {stats["total_docs"]}')
    print(f'  Total unique terms:       {stats["unique_terms"]}')
    print(f'  Total failed URLs:        {crawl_manager.pages_failed}')
    print(f'  Elapsed time:             {elapsed:.2f} seconds')

    if index_path and os.path.exists(index_path):
        size_bytes = os.path.getsize(index_path)
        if size_bytes >= 1024 * 1024:
            size_str = f'{size_bytes / (1024 * 1024):.2f} MB'
        elif size_bytes >= 1024:
            size_str = f'{size_bytes / 1024:.2f} KB'
        else:
            size_str = f'{size_bytes} bytes'
        print(f'  Index file size:          {size_str}')

    # Top 10 most linked domains
    top_domains = crawl_manager.get_top_domains(10)
    if top_domains:
        print('\n  Top 10 most linked domains:')
        for i, (domain, count) in enumerate(top_domains, 1):
            print(f'    {i:2d}. {domain:<40s} {count:5d} links')

    # Failed URLs (show first 5)
    failed = crawl_manager.get_failed_urls()
    if failed:
        print(f'\n  Failed URLs ({len(failed)} total, showing first 5):')
        for url, error in failed[:5]:
            print(f'    - {url}')
            print(f'      Error: {error}')

    print('=' * 60)
