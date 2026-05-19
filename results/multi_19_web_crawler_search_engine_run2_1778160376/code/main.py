#!/usr/bin/env python3
"""
Web Crawler Search Engine – main entry point.

Usage:
  python main.py --seeds seeds.txt [--depth 2] [--limit 100] [--workers 5]
                 [--timeout 10] [--port 8080] [--serve] [--load-index index.json]
"""

import argparse
import sys
import os
import time
import logging
from pathlib import Path

from utils import normalize_url, configure_logging, ProgressMonitor
from indexer import Indexer
from crawler import Crawler
from search_engine import SearchEngine
from html_generator import generate_search_html
from api_server import run_server

logger = logging.getLogger(__name__)


def read_seed_file(path: str) -> list[str]:
    """Read seed URLs from a file, one per line."""
    seeds = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                url = normalize_url(line)
                if url:
                    seeds.append(url)
                else:
                    logger.warning("Skipping invalid seed URL: %s", line)
    return seeds


def main():
    parser = argparse.ArgumentParser(
        description="Web Crawler Search Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --seeds seeds.txt
  python main.py --seeds seeds.txt --depth 3 --limit 200 --serve
  python main.py --load-index index.json --serve
        """,
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Path to seed file with one URL per line",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Maximum crawl depth (default: 2)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of pages to crawl (default: 100)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of concurrent crawler workers (default: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="API server port (default: 8080)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        default=False,
        help="Start the REST API server after crawling",
    )
    parser.add_argument(
        "--load-index",
        type=str,
        default=None,
        help="Load an existing index from a JSON file instead of crawling",
    )
    parser.add_argument(
        "--index-file",
        type=str,
        default="index.json",
        help="Path to save/load the index JSON file (default: index.json)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.seeds and not args.load_index:
        parser.error("Either --seeds or --load-index must be provided")

    configure_logging()

    search_engine = None
    crawl_duration = 0.0
    indexer = None
    seed_urls = []

    # Load existing index if requested
    if args.load_index:
        index_path = args.load_index
        if not os.path.exists(index_path):
            print(f"Error: Index file not found: {index_path}")
            sys.exit(1)

        print(f"Loading index from {index_path}...")
        indexer = Indexer()
        indexer.load(index_path)
        search_engine = SearchEngine(indexer)
        crawl_duration = 0.0  # Not available from loaded index
        print(f"Loaded index: {indexer.doc_count} pages, {indexer.total_terms} unique terms")

        # Read seeds from the seed file for potential re-crawl
        if args.seeds:
            seed_urls = read_seed_file(args.seeds)
            print(f"Read {len(seed_urls)} seed URLs for potential re-crawl")
    else:
        # Read seed file
        if not os.path.exists(args.seeds):
            print(f"Error: Seed file not found: {args.seeds}")
            sys.exit(1)

        seed_urls = read_seed_file(args.seeds)
        if not seed_urls:
            print("Error: No valid seed URLs found in seed file")
            sys.exit(1)

        print(f"Starting crawl with {len(seed_urls)} seed URLs...")
        print(f"Depth: {args.depth}, Limit: {args.limit}, Workers: {args.workers}")
        print()

        # Progress monitor
        progress = ProgressMonitor()

        # Create and run crawler
        crawler = Crawler(
            seed_urls=seed_urls,
            depth=args.depth,
            limit=args.limit,
            num_workers=args.workers,
            timeout=args.timeout,
            progress_callback=progress.update,
        )

        start = time.time()
        indexer = crawler.run()
        crawl_duration = time.time() - start
        progress.finish()

        # Print summary
        print()
        print("=" * 60)
        print("CRAWL SUMMARY")
        print("=" * 60)
        print(f"  Total pages crawled:  {indexer.doc_count}")
        print(f"  Total unique terms:   {indexer.total_terms}")
        print(f"  Crawl duration:       {crawl_duration:.2f} seconds")
        print(f"  Failed URLs:          {crawler.failed}")

        # Top 10 most linked domains
        top_domains = crawler.get_top_domains(10)
        if top_domains:
            print()
            print("  Top 10 most linked domains:")
            for i, (domain, count) in enumerate(top_domains, 1):
                print(f"    {i:2}. {domain} ({count} links)")
        print("=" * 60)

        # Save index
        index_path = args.index_file
        print(f"\nSaving index to {index_path}...")
        indexer.save(index_path)
        index_size = os.path.getsize(index_path)
        print(f"Index saved ({index_size:,} bytes)")

        # Create search engine
        search_engine = SearchEngine(indexer)

    # Generate search.html
    generate_search_html(args.port)

    # Start server if requested
    if args.serve:
        run_server(
            port=args.port,
            search_engine=search_engine,
            seed_urls=seed_urls,
            depth=args.depth,
            limit=args.limit,
            workers=args.workers,
            timeout=args.timeout,
            crawl_duration=crawl_duration,
            index_file_path=args.index_file if not args.load_index else args.load_index,
        )
    else:
        # If not serving, do a quick interactive search demo
        if search_engine:
            print("\n" + "=" * 60)
            print("Index ready. Use --serve to start the web interface,")
            print("or enter a query below to test search (Ctrl+C to exit):")
            print("=" * 60)
            try:
                while True:
                    query = input("\nQuery> ").strip()
                    if not query:
                        continue
                    results = search_engine.search(query, limit=10)
                    if not results:
                        print("  No results found.")
                    else:
                        for i, r in enumerate(results, 1):
                            print(f"\n  {i}. {r['title'] or 'Untitled'}")
                            print(f"     URL: {r['url']}")
                            print(f"     Score: {r['score']:.4f}")
                            # Strip HTML tags from snippet for terminal display
                            import re
                            clean_snippet = re.sub(r"<[^>]+>", "", r["snippet"])
                            print(f"     {clean_snippet[:120]}...")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")


if __name__ == "__main__":
    main()
