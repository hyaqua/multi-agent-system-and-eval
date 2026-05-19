#!/usr/bin/env python3
"""Web Crawler and Full-Text Search Engine - Main Entry Point.

Usage:
    python main.py --seeds seeds.txt --depth 2 --limit 100 --workers 5 --serve 8080
    python main.py --load-index index.json --serve 8080
"""

import argparse
import logging
import os
import sys
import time

from url_utils import normalize_url, get_domain
from crawler import CrawlManager
from indexer import InvertedIndex
from reporter import CrawlReporter
from server import SearchAPIServer, generate_search_html


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
    )
    # Suppress urllib debug
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def read_seeds(filepath: str) -> list:
    """Read seed URLs from a plaintext file, one per line."""
    if not os.path.exists(filepath):
        print(f"Error: Seeds file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    seeds = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                normalized = normalize_url(line)
                if normalized:
                    seeds.append(normalized)
                else:
                    print(f"Warning: Skipping invalid URL: {line}", file=sys.stderr)

    if not seeds:
        print(f"Error: No valid seed URLs found in {filepath}", file=sys.stderr)
        sys.exit(1)

    return seeds


def generate_search_html_file():
    """Write the search.html file to the current directory."""
    html = generate_search_html()
    filepath = os.path.join(os.getcwd(), "search.html")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Generated: {filepath}")
    except PermissionError:
        # Try /tmp
        filepath = "/tmp/search.html"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Generated: {filepath}")
    except Exception as e:
        print(f"Warning: Could not write search.html: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Web Crawler and Full-Text Search Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --seeds seeds.txt
  python main.py --seeds seeds.txt --depth 3 --limit 200 --workers 8
  python main.py --seeds seeds.txt --serve 8080
  python main.py --load-index index.json --serve 8080
        """,
    )

    # Seed/Index options
    parser.add_argument(
        "--seeds",
        type=str,
        default="",
        help="Path to plaintext file with one seed URL per line",
    )
    parser.add_argument(
        "--load-index",
        type=str,
        default="",
        help="Load an existing index from JSON file instead of crawling",
    )

    # Crawl options
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

    # Output/Serve options
    parser.add_argument(
        "--save-index",
        type=str,
        default="index.json",
        help="Path to save the index JSON file (default: index.json)",
    )
    parser.add_argument(
        "--serve",
        type=int,
        default=0,
        help="Start REST API server on the given port after crawling",
    )

    # Miscellaneous
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not persist the index to disk",
    )

    args = parser.parse_args()

    setup_logging()

    # Generate search.html file
    generate_search_html_file()

    index: InvertedIndex = None
    crawl_duration = 0.0
    seeds = []
    crawl_manager = None

    # Load existing index if specified
    if args.load_index:
        print(f"Loading index from {args.load_index}...")
        if not os.path.exists(args.load_index):
            print(f"Error: Index file not found: {args.load_index}", file=sys.stderr)
            sys.exit(1)
        index = InvertedIndex.load(args.load_index)
        print(f"Loaded index with {index.doc_count} documents and {index.term_count} terms.")

        # Also load seeds from the file used to create this index (optional)
        if args.seeds:
            seeds = read_seeds(args.seeds)
        else:
            seeds = list(index.documents.keys())[:10]  # Use first 10 docs as seeds

        # Create crawl manager for /crawl API endpoint
        if seeds:
            crawl_manager = CrawlManager(
                seeds=seeds,
                depth=args.depth,
                limit=args.limit,
                workers=args.workers,
                timeout=args.timeout,
                index=index,
            )
        else:
            crawl_manager = None

    elif args.seeds:
        # Read seeds and crawl
        seeds = read_seeds(args.seeds)
        print(f"Loaded {len(seeds)} seed URL(s).")
        print(f"Crawl depth: {args.depth}, Page limit: {args.limit}, Workers: {args.workers}")
        print()

        # Create reporter and crawler
        reporter = CrawlReporter()
        index = InvertedIndex()

        # Create crawler for later use in crawl jobs
        crawl_manager = CrawlManager(
            seeds=seeds,
            depth=args.depth,
            limit=args.limit,
            workers=args.workers,
            timeout=args.timeout,
            index=index,
            reporter=reporter,
        )

        # Run the crawl
        start_time = time.time()
        index = crawl_manager.crawl()
        crawl_duration = time.time() - start_time

        # Save index
        if not args.no_save:
            save_path = args.save_index
            index.save(save_path)
            print(f"Index saved to: {save_path}")

        crawl_duration = crawl_manager._end_time - crawl_manager._start_time if crawl_manager._start_time and crawl_manager._end_time else crawl_duration

        # Create crawl manager for future /crawl API calls
        # (reusing the same manager)
    else:
        # No seeds and no index - create empty index for serving
        print("No --seeds or --load-index specified. Starting with empty index.")
        index = InvertedIndex()
        crawl_manager = None
        seeds = []

    # Start server if requested
    if args.serve:
        server = SearchAPIServer(
            index=index,
            crawl_manager=crawl_manager,
            seeds=seeds,
            depth=args.depth,
            limit=args.limit,
            workers=args.workers,
            timeout=args.timeout,
            crawl_duration=crawl_duration,
        )
        server.start(args.serve)
    else:
        # If not serving, do a quick test search prompt
        if index and index.doc_count > 0:
            print()
            print("Index is ready. Start the server with --serve PORT to search.")
            print(f"  Example: python {sys.argv[0]} --load-index {args.save_index} --serve 8080")


if __name__ == "__main__":
    main()
