#!/usr/bin/env python3
"""
Web Crawler and Full-Text Search Engine

Usage:
    python main.py --seeds seeds.txt [options]

Options:
    --seeds FILE      Path to seed URLs file (one URL per line)
    --depth N         Crawl depth (default: 2)
    --limit N         Max pages to crawl (default: 100)
    --workers N       Number of worker threads (default: 5)
    --timeout N       Request timeout in seconds (default: 10)
    --output FILE     Path to save index JSON (default: index.json)
    --load-index FILE Load existing index from JSON file
    --serve           Start REST API server after crawling
    --port N          Port for REST API (default: 8080)
    --generate-html   Generate search.html interface
    --html-path PATH  Path for generated HTML (default: search.html)
    --log-level       Set logging level (default: WARNING)
"""

import argparse
import logging
import os
import sys
import time

from crawler.crawler import Crawler
from crawler.indexer import Indexer
from crawler.server import run_server, generate_search_html


def parse_args():
    parser = argparse.ArgumentParser(
        description='Web Crawler and Full-Text Search Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--seeds', type=str, default=None,
                        help='Path to seed URLs file (one URL per line)')
    parser.add_argument('--depth', type=int, default=2,
                        help='Crawl depth (default: 2)')
    parser.add_argument('--limit', type=int, default=100,
                        help='Max pages to crawl (default: 100)')
    parser.add_argument('--workers', type=int, default=5,
                        help='Number of worker threads (default: 5)')
    parser.add_argument('--timeout', type=int, default=10,
                        help='Request timeout in seconds (default: 10)')
    parser.add_argument('--output', type=str, default='/tmp/index.json',
                        help='Path to save index JSON (default: /tmp/index.json)')
    parser.add_argument('--load-index', type=str, default=None,
                        help='Load existing index from JSON file')
    parser.add_argument('--serve', action='store_true', default=False,
                        help='Start REST API server after crawling')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for REST API (default: 8080)')
    parser.add_argument('--generate-html', action='store_true', default=False,
                        help='Generate search.html interface')
    parser.add_argument('--html-path', type=str, default='/tmp/search.html',
                        help='Path for generated HTML (default: /tmp/search.html)')
    parser.add_argument('--log-level', type=str, default='WARNING',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Set logging level (default: WARNING)')
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='[%(levelname)s] %(message)s'
    )
    
    indexer = None
    crawl_duration = 0.0
    index_file_path = args.output
    index_file_size = 0
    
    # Load existing index if specified
    if args.load_index:
        print(f"Loading index from {args.load_index}...")
        indexer = Indexer()
        try:
            loaded_duration = indexer.load(args.load_index)
            index_file_path = args.load_index
            index_file_size = os.path.getsize(args.load_index)
            crawl_duration = loaded_duration if loaded_duration > 0 else crawl_duration
            print(f"Loaded index: {indexer.doc_count} documents, {len(indexer.index)} terms")
        except Exception as e:
            print(f"Error loading index: {e}")
            sys.exit(1)
    
    # Crawl if seeds provided and not just loading
    if args.seeds and not args.load_index:
        # Read seed URLs
        try:
            with open(args.seeds, 'r') as f:
                seed_urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: Seed file '{args.seeds}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading seed file: {e}")
            sys.exit(1)
        
        if not seed_urls:
            print("Error: Seed file is empty.")
            sys.exit(1)
        
        print(f"Loaded {len(seed_urls)} seed URL(s) from {args.seeds}")
        print(f"Configuration: depth={args.depth}, limit={args.limit}, workers={args.workers}, timeout={args.timeout}s")
        print()
        
        # Run crawler
        start_time = time.time()
        crawler = Crawler(
            seed_urls=seed_urls,
            depth=args.depth,
            max_pages=args.limit,
            num_workers=args.workers,
            timeout=args.timeout
        )
        
        try:
            indexer = crawler.crawl()
        except KeyboardInterrupt:
            print("\nCrawl interrupted by user.")
            crawler.stats.running = False
            indexer = crawler.indexer
        
        crawl_duration = time.time() - start_time
        
        # Save index
        if indexer:
            try:
                indexer.save(args.output, crawl_duration=crawl_duration)
                index_file_size = os.path.getsize(args.output)
                print(f"\nIndex saved to {args.output} ({index_file_size} bytes)")
            except Exception as e:
                print(f"Error saving index: {e}")
    
    # Generate HTML interface
    if args.generate_html:
        try:
            generate_search_html(args.html_path)
        except Exception as e:
            print(f"Warning: Could not generate HTML: {e}")
    
    # Start server if requested
    if args.serve:
        if indexer is None:
            indexer = Indexer()
        
        # Generate HTML if not already done (default to generating when serving)
        if not args.generate_html:
            try:
                generate_search_html(args.html_path)
            except Exception as e:
                print(f"Warning: Could not generate HTML: {e}")
        
        run_server(
            indexer=indexer,
            port=args.port,
            seed_file=args.seeds,
            crawl_depth=args.depth,
            crawl_limit=args.limit,
            crawl_workers=args.workers,
            crawl_timeout=args.timeout,
            crawl_duration=crawl_duration,
            index_file_size=index_file_size,
            html_path=args.html_path
        )
    elif not args.load_index and not args.seeds:
        print("Nothing to do. Use --seeds to crawl, --load-index to load an index, or --serve to start the server.")
        print("Example: python main.py --seeds seeds.txt --depth 2 --limit 50 --serve")


if __name__ == '__main__':
    main()
