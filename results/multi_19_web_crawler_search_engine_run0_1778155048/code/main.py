#!/usr/bin/env python3
"""CLI entry point for the Web Crawler & Search Engine."""

import argparse
import sys
import os
import time
import threading
from collections import Counter

from crawler import Crawler
from indexer import Indexer
from search_engine import SearchEngine
from crawl_stats import CrawlStats
from url_utils import normalize_url, get_domain
from html_generator import generate_search_html


def read_seeds(filepath):
    """Read seed URLs from a file, one per line."""
    seeds = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    seeds.append(line)
    except FileNotFoundError:
        print(f"ERROR: Seeds file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    return seeds


def print_summary(documents, indexer, crawl_stats, elapsed):
    """Print a summary report after crawling."""
    print("\n" + "=" * 60)
    print("  CRAWL SUMMARY")
    print("=" * 60)
    print(f"  Total pages crawled:    {len(documents)}")
    print(f"  Total unique terms:     {len(indexer.inverted_index)}")
    print(f"  Elapsed time:           {elapsed:.2f} seconds")

    # Top 10 most linked domains
    from url_utils import get_domain
    from collections import Counter

    link_domain_counter = Counter()
    for doc in documents:
        outlinks = doc.get('outlinks', [])
        if isinstance(outlinks, list):
            for link in outlinks:
                try:
                    domain = get_domain(link)
                    if domain:
                        link_domain_counter[domain] += 1
                except Exception:
                    pass

    top_domains = link_domain_counter.most_common(10)
    if top_domains:
        print(f"\n  Top 10 most linked domains:")
        for i, (domain, count) in enumerate(top_domains, 1):
            print(f"    {i:2}. {domain:<40} ({count} links)")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Web Crawler & Search Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --seeds seeds.txt
  python main.py --seeds seeds.txt --serve --port 8080
  python main.py --seeds seeds.txt --depth 3 --limit 500 --workers 10
  python main.py --load-index index.json --serve
        """
    )

    # Crawl configuration
    parser.add_argument('--seeds', type=str, default=None,
                        help='File containing seed URLs (one per line)')
    parser.add_argument('--depth', type=int, default=2,
                        help='Maximum crawl depth (default: 2)')
    parser.add_argument('--limit', type=int, default=100,
                        help='Maximum pages to crawl (default: 100)')
    parser.add_argument('--workers', type=int, default=5,
                        help='Number of concurrent crawler workers (default: 5)')
    parser.add_argument('--timeout', type=int, default=10,
                        help='HTTP request timeout in seconds (default: 10)')

    # Server configuration
    parser.add_argument('--serve', action='store_true',
                        help='Start REST API server after crawl')
    parser.add_argument('--port', type=int, default=8080,
                        help='Server port (default: 8080)')

    # Index configuration
    parser.add_argument('--load-index', type=str, default=None,
                        help='Load existing index JSON file instead of crawling')
    parser.add_argument('--index-file', type=str, default='index.json',
                        help='Path to save/load index JSON (default: index.json)')

    args = parser.parse_args()

    # Validate arguments
    if not args.seeds and not args.load_index:
        parser.error("Either --seeds or --load-index must be specified.")

    if args.load_index and args.seeds:
        print("NOTE: Both --seeds and --load-index specified. Using --load-index, ignoring --seeds.")

    seed_urls = []
    if args.seeds:
        seed_urls = read_seeds(args.seeds)
        if not seed_urls:
            print("ERROR: No valid seed URLs found in the seeds file.", file=sys.stderr)
            sys.exit(1)
        print(f"Loaded {len(seed_urls)} seed URL(s) from {args.seeds}")

    index_file = args.index_file

    # Mode 1: Load existing index
    if args.load_index:
        index_file = args.load_index
        print(f"Loading index from {index_file}...")
        engine = SearchEngine()
        engine.load_index(index_file)
        print(f"Loaded {engine.indexer.doc_count} documents, "
              f"{len(engine.indexer.inverted_index)} unique terms.")

        # Set as global search engine for server
        import server as server_module
        server_module.search_engine = engine
        server_module.global_stats.update(engine.get_stats(index_file))
        server_module.server_config['index_file'] = index_file

        if args.serve:
            generate_search_html('search.html', args.port)

            # Seed URLs for potential recrawl
            if seed_urls:
                server_module.server_config['seed_urls'] = seed_urls
            server_module.server_config.update({
                'port': args.port,
                'max_depth': args.depth,
                'max_pages': args.limit,
                'num_workers': args.workers,
                'timeout': args.timeout,
            })
            server_module.run_server(args.port)
        else:
            # Interactive search mode
            print("\nEntering interactive search mode. Type 'quit' to exit.\n")
            while True:
                try:
                    query = input("Search> ").strip()
                    if query.lower() in ('quit', 'exit', 'q'):
                        break
                    if not query:
                        continue
                    results = engine.search(query, limit=10)
                    if not results:
                        print("  No results found.")
                    else:
                        for i, r in enumerate(results, 1):
                            print(f"\n  {i}. {r['title']}")
                            print(f"     URL: {r['url']}")
                            print(f"     Score: {r['score']:.4f}")
                            # Strip HTML from snippet for terminal
                            import re
                            snippet = re.sub(r'<[^>]+>', '', r['snippet'])
                            print(f"     {snippet[:120]}...")
                except (EOFError, KeyboardInterrupt):
                    print("\n")
                    break
        return

    # Mode 2: Crawl first
    print(f"\nStarting crawl:")
    print(f"  Seeds: {len(seed_urls)} URL(s)")
    print(f"  Max depth: {args.depth}")
    print(f"  Max pages: {args.limit}")
    print(f"  Workers: {args.workers}")
    print(f"  Timeout: {args.timeout}s")
    print()

    # Initialize components
    crawl_stats = CrawlStats()
    indexer = Indexer()

    crawler = Crawler(
        seed_urls=seed_urls,
        max_depth=args.depth,
        max_pages=args.limit,
        num_workers=args.workers,
        timeout=args.timeout,
        stats=crawl_stats
    )

    # Run crawl
    start_time = time.time()
    documents = crawler.crawl()
    elapsed = time.time() - start_time

    if not documents:
        print("\nNo documents crawled. Check your seed URLs and network connection.")
        sys.exit(1)

    # Build index
    print("\nBuilding search index...")
    indexer.add_documents_batch(documents)
    indexer.build_index()

    # Save index
    indexer.save_to_file(index_file)

    # Create search engine
    engine = SearchEngine(indexer)

    # Print summary
    print_summary(documents, indexer, crawl_stats, elapsed)

    # Set global server configuration
    import server as server_module
    server_module.search_engine = engine
    server_module.global_stats.update(engine.get_stats(index_file))
    server_module.global_stats['crawl_duration_seconds'] = elapsed
    server_module.server_config.update({
        'index_file': index_file,
        'seed_urls': seed_urls,
        'port': args.port,
        'seeds_file': args.seeds,
        'max_depth': args.depth,
        'max_pages': args.limit,
        'num_workers': args.workers,
        'timeout': args.timeout,
    })

    # Generate search.html
    generate_search_html('search.html', args.port)

    # Mode 2a: Start server
    if args.serve:
        server_module.run_server(args.port)
    else:
        # Interactive search mode
        print("\nEntering interactive search mode. Type 'quit' to exit.\n")
        while True:
            try:
                query = input("Search> ").strip()
                if query.lower() in ('quit', 'exit', 'q'):
                    break
                if not query:
                    continue
                results = engine.search(query, limit=10)
                if not results:
                    print("  No results found.")
                else:
                    for i, r in enumerate(results, 1):
                        print(f"\n  {i}. {r['title']}")
                        print(f"     URL: {r['url']}")
                        print(f"     Score: {r['score']:.4f}")
                        import re
                        snippet = re.sub(r'<[^>]+>', '', r['snippet'])
                        print(f"     {snippet[:120]}...")
            except (EOFError, KeyboardInterrupt):
                print("\n")
                break


if __name__ == '__main__':
    main()
