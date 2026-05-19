"""
startup.py – Launcher script that starts the router and a configurable number of nodes.

Usage:
    python startup.py --router-port 7000 --num-nodes 3 [--virtual-nodes 128]
"""

import subprocess
import sys
import time
import argparse
import os
import signal


def main():
    parser = argparse.ArgumentParser(description="Launch distributed KV store")
    parser.add_argument("--router-port", type=int, default=7000,
                        help="Port for router to listen on (default: 7000)")
    parser.add_argument("--num-nodes", type=int, default=3,
                        help="Number of storage nodes to launch (default: 3)")
    parser.add_argument("--virtual-nodes", type=int, default=128,
                        help="Virtual nodes per physical node (default: 128)")
    parser.add_argument("--health-interval", type=float, default=2.0,
                        help="Router health check interval in seconds (default: 2.0)")
    parser.add_argument("--health-timeout", type=float, default=1.0,
                        help="Health check timeout in seconds (default: 1.0)")
    parser.add_argument("--log-level", default="INFO",
                        help="Log level (default: INFO)")
    args = parser.parse_args()

    processes: list[subprocess.Popen] = []

    def cleanup():
        print("\nShutting down all processes...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        # Give them time to terminate
        time.sleep(1)
        for p in processes:
            try:
                p.kill()
            except Exception:
                pass

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 1. Start the router
    print(f"Starting router on port {args.router_port}...")
    router_cmd = [
        sys.executable, "router.py",
        "--port", str(args.router_port),
        "--virtual-nodes", str(args.virtual_nodes),
        "--health-interval", str(args.health_interval),
        "--health-timeout", str(args.health_timeout),
        "--log-level", args.log_level,
    ]
    router_proc = subprocess.Popen(router_cmd)
    processes.append(router_proc)
    print(f"  Router PID: {router_proc.pid}")

    # Give the router a moment to start
    time.sleep(1)

    # 2. Start nodes
    print(f"Starting {args.num_nodes} storage node(s)...")
    for i in range(args.num_nodes):
        node_cmd = [
            sys.executable, "node.py",
            "localhost",
            str(args.router_port),
            "--log-level", args.log_level,
        ]
        node_proc = subprocess.Popen(node_cmd)
        processes.append(node_proc)
        print(f"  Node {i} PID: {node_proc.pid}")
        # Small stagger to avoid all registering at exactly the same time
        time.sleep(0.3)

    print(f"\nAll processes running. Router on localhost:{args.router_port}")
    print("Press Ctrl+C to stop all processes.\n")

    # Wait for all processes
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
