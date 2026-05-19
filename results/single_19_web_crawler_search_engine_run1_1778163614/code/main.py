#!/usr/bin/env python3
"""Web Crawler and Full-Text Search Engine.

Usage:
    python main.py --seeds seeds.txt [--depth 2] [--limit 100] [--workers 5]
                   [--serve] [--port 8080] [--load-index index.json]
"""

import argparse
import os
import sys
import time
import threading
import signal

from indexer import Indexer
from crawler import Crawler
from server import start_server, generate_search_html


def read_seeds(path: str) -> list[str]:
    """Read seed URLs from a plaintext file, one per line."""
    if not os.path.exists(path):
        print(f'Error: Seed file not found: {path}', file=sys.stderr)
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        seeds = []
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                seeds.append(line)
    return seeds


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Async web crawler and full-text search engine'
    )
    parser.add_argument('--seeds', type=str, default='seeds.txt',
                        help='Path to file with seed URLs (one per line)')
    parser.add_argument('--depth', type=int, default=2,
                        help='Maximum crawl depth (default: 2)')
    parser.add_argument('--limit', type=int, default=100,
                        help='Maximum number of pages to crawl (default: 100)')
    parser.add_argument('--workers', type=int, default=5,
                        help='Number of concurrent crawler workers (default: 5)')
    parser.add_argument('--timeout', type=float, default=10.0,
                        help='Fetch timeout in seconds (default: 10)')
    parser.add_argument('--serve', action='store_true', default=False,
                        help='Start REST API server after crawling')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for the REST API server (default: 8080)')
    parser.add_argument('--load-index', type=str, default=None,
                        help='Load index from JSON file instead of crawling')
    parser.add_argument('--save-index', type=str, default='index.json',
                        help='Path to save the index JSON (default: index.json)')
    parser.add_argument('--output-html', type=str, default='search.html',
                        help='Path for generated search HTML (default: search.html)')

    args = parser.parse_args()

    indexer = Indexer()

    # Load or crawl
    if args.load_index:
        print(f'Loading index from {args.load_index}...')
        if not indexer.load(args.load_index):
            print(f'Error: Failed to load index from {args.load_index}', file=sys.stderr)
            sys.exit(1)
        print(f'Loaded index: {indexer.doc_count} pages, '
              f'{len(indexer.inverted_index)} unique terms')
    else:
        seeds = read_seeds(args.seeds)
        if not seeds:
            print('Error: No seed URLs found.', file=sys.stderr)
            sys.exit(1)

        print(f'Starting crawl with {len(seeds)} seed URLs...')
        print(f'  Depth: {args.depth}, Limit: {args.limit}, Workers: {args.workers}')
        print()

        crawler = Crawler(
            seeds=seeds,
            depth=args.depth,
            limit=args.limit,
            workers=args.workers,
            timeout=args.timeout,
            indexer=indexer,
        )

        start = time.time()
        indexer = crawler.run()
        elapsed = time.time() - start

        # Print summary
        print()
        print(crawler.get_summary())

        # Save index
        save_path = args.save_index or 'index.json'
        indexer.save(save_path)
        save_size = os.path.getsize(save_path) if os.path.exists(save_path) else 0
        print(f'\nIndex saved to {save_path} ({save_size:,} bytes)')

    # Generate search HTML
    html_path = args.output_html or 'search.html'
    html_content = generate_search_html(args.port)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'Search interface generated at {html_path}')

    # Start server if requested
    if args.serve:
        server = start_server(
            indexer=indexer,
            seed_file=args.seeds,
            port=args.port,
            depth=args.depth,
            limit=args.limit,
            workers=args.workers,
        )

        print(f'\nREST API server starting on http://localhost:{args.port}')
        print(f'  Endpoints:')
        print(f'    GET /search?q=query&limit=N  - Search the index')
        print(f'    GET /stats                    - Index statistics')
        print(f'    GET /crawl                    - Start new crawl')
        print(f'    GET /crawl/{{job_id}}           - Crawl job status')
        print(f'\nPress Ctrl+C to stop the server.')

        # Handle graceful shutdown
        shutdown_event = threading.Event()

        def _sig_handler(signum, frame):
            print('\nShutting down...')
            shutdown_event.set()

        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)

        # Run server in a thread so we can handle signals
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        try:
            while not shutdown_event.is_set():
                shutdown_event.wait(0.5)
        except KeyboardInterrupt:
            pass

        server.shutdown()
        server.server_close()
        print('Server stopped.')


if __name__ == '__main__':
    main()
