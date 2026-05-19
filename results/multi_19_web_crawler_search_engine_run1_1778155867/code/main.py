#!/usr/bin/env python3
"""
Simple Web Crawler & Search Engine

A full-featured web crawler and search engine using only the Python
standard library. Crawls websites, builds an inverted index with TF-IDF
scoring, and provides a REST API and static search interface.

Usage:
    python main.py --seeds seeds.txt --depth 2 --limit 100 --workers 5 --serve --port 8080
    python main.py --load-index index.json --serve --port 8080
"""

import argparse
import time
import os
import sys

from url_utils import URLUtils
from indexer import Indexer
from searcher import Searcher
from crawl_manager import CrawlManager
from server import run_server
from html_generator import generate_search_html
from utils import print_summary


def read_seeds(filepath: str) -> list[str]:
    """Read seed URLs from a file, one URL per line."""
    seeds = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    seeds.append(line)
    except FileNotFoundError:
        print(f'Error: Seeds file not found: {filepath}')
        sys.exit(1)
    except Exception as e:
        print(f'Error reading seeds file: {e}')
        sys.exit(1)

    if not seeds:
        print(f'Warning: No seeds found in {filepath}')

    return seeds


def main():
    parser = argparse.ArgumentParser(
        description='Simple Web Crawler & Search Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--seeds',
        type=str,
        default='seeds.txt',
        help='Path to file containing seed URLs (one per line). Default: seeds.txt',
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=2,
        help='Maximum crawl depth. Default: 2',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of pages to crawl. Default: 100',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Number of concurrent crawler threads. Default: 5',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='HTTP request timeout in seconds. Default: 10',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port for the REST API server. Default: 8080',
    )
    parser.add_argument(
        '--serve',
        action='store_true',
        help='Start the REST API server after crawling.',
    )
    parser.add_argument(
        '--load-index',
        type=str,
        default=None,
        help='Load an existing index JSON file instead of crawling.',
    )
    parser.add_argument(
        '--index-path',
        type=str,
        default='index.json',
        help='Path to save/load the index JSON file. Default: index.json',
    )
    parser.add_argument(
        '--no-crawl',
        action='store_true',
        help='Skip crawling entirely (only serve if --serve is set with --load-index).',
    )

    args = parser.parse_args()

    # Generate search.html
    if not generate_search_html('search.html'):
        print('Warning: search.html could not be created. '
              'The REST API remains available.', file=sys.stderr)

    # Create shared components
    url_utils = URLUtils()
    indexer = Indexer()
    searcher = Searcher(indexer)
    crawl_manager = CrawlManager(
        indexer=indexer,
        url_utils=url_utils,
        num_workers=args.workers,
        timeout=args.timeout,
        depth=args.depth,
        limit=args.limit,
    )

    crawl_duration = 0.0

    if args.load_index:
        # Load existing index
        print(f'Loading index from {args.load_index}...')
        try:
            indexer.load(args.load_index)
            stats = indexer.get_stats()
            print(f'Loaded index with {stats["total_docs"]} documents and '
                  f'{stats["unique_terms"]} unique terms.')
            args.index_path = args.load_index
        except FileNotFoundError:
            print(f'Error: Index file not found: {args.load_index}')
            sys.exit(1)
        except Exception as e:
            print(f'Error loading index: {e}')
            sys.exit(1)

    if not args.no_crawl and not args.load_index:
        # Read seeds and start crawling
        seeds = read_seeds(args.seeds)
        if not seeds:
            print('No seed URLs to crawl. Exiting.')
            if args.serve:
                print('Starting server with empty index...')
            else:
                sys.exit(0)

        print(f'Starting crawl with {len(seeds)} seed(s), '
              f'depth={args.depth}, limit={args.limit}, '
              f'workers={args.workers}, timeout={args.timeout}s')
        print()

        start_time = time.time()

        print('Crawling...')
        crawl_manager.start_crawl(
            seeds=seeds,
            depth=args.depth,
            limit=args.limit,
        )

        crawl_duration = time.time() - start_time

        # Print summary (always, before file writes)
        print_summary(crawl_manager, indexer, crawl_duration, args.index_path)

        # Save index (non-fatal)
        print(f'\nSaving index to {args.index_path}...')
        if indexer.save(args.index_path):
            print('Index saved.')
        else:
            print('Warning: Index could not be written to disk. '
                  'Serving continues from memory.')

    elif args.load_index:
        # Already loaded, just compute TF-IDF if vectors not present
        if not indexer.tfidf_vectors:
            print('Computing TF-IDF scores...')
            indexer.compute_tfidf()
            if indexer.save(args.index_path):
                print('Index saved.')
            else:
                print('Warning: Index could not be written to disk. '
                      'Serving continues from memory.')
            print('Done.')

    # Start server if requested
    if args.serve:
        # Get seeds for potential re-crawl via API
        seeds = []
        if os.path.exists(args.seeds):
            seeds = read_seeds(args.seeds)

        run_server(
            port=args.port,
            indexer=indexer,
            searcher=searcher,
            crawl_manager=crawl_manager,
            seeds=seeds,
            index_path=args.index_path,
            crawl_duration=crawl_duration,
        )


if __name__ == '__main__':
    main()
