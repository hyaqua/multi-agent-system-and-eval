#!/usr/bin/env python3
"""Startup script: launches the router and a configurable number of storage nodes."""

import sys
import time
import signal
import argparse
import multiprocessing


def run_router(host: str, port: int, vnodes: int, health_interval: float, health_timeout: float):
    """Entry point for the router process."""
    from router import Router
    router = Router(
        host=host,
        port=port,
        vnodes_per_node=vnodes,
        health_check_interval=health_interval,
        health_check_timeout=health_timeout,
    )
    try:
        router.start()
    except KeyboardInterrupt:
        pass


def run_node(router_host: str, router_port: int):
    """Entry point for a storage node process."""
    from storage_node import StorageNode
    # Add a small delay so nodes don't all connect at exactly the same time
    time.sleep(0.1)
    node = StorageNode(router_host=router_host, router_port=router_port)
    try:
        node.start()
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Start the distributed key-value store (router + storage nodes)"
    )
    parser.add_argument("--host", default="localhost", help="Router host (default: localhost)")
    parser.add_argument("--port", type=int, default=7000, help="Router port (default: 7000)")
    parser.add_argument("--nodes", type=int, default=3, help="Number of storage nodes (default: 3)")
    parser.add_argument("--vnodes", type=int, default=100, help="Virtual nodes per storage node (default: 100)")
    parser.add_argument("--health-interval", type=float, default=5.0, help="Health check interval in seconds (default: 5)")
    parser.add_argument("--health-timeout", type=float, default=3.0, help="Health check timeout in seconds (default: 3)")
    args = parser.parse_args()

    processes: list[multiprocessing.Process] = []

    def cleanup():
        """Terminate all child processes."""
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join(timeout=2)
        print("\nAll processes stopped.")

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda sig, frame: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: cleanup() or sys.exit(0))

    print(f"Starting router on {args.host}:{args.port}...")
    router_proc = multiprocessing.Process(
        target=run_router,
        args=(args.host, args.port, args.vnodes, args.health_interval, args.health_timeout),
        name="router",
    )
    router_proc.start()
    processes.append(router_proc)

    # Wait for router to start
    time.sleep(0.5)

    print(f"Starting {args.nodes} storage node(s)...")
    for i in range(args.nodes):
        node_proc = multiprocessing.Process(
            target=run_node,
            args=(args.host, args.port),
            name=f"node-{i+1}",
        )
        node_proc.start()
        processes.append(node_proc)
        time.sleep(0.05)  # Small stagger

    print(f"All processes started. Use the CLI client to interact:")
    print(f"  python client.py")
    print(f"  python client.py --port {args.port}")
    print()
    print("Press Ctrl+C to stop all processes.")

    try:
        # Wait for all processes
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
