"""
start.py — Startup script.

Launches the router process and a configurable number of storage node
processes using subprocess.
"""
import argparse
import subprocess
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Start KV Store cluster")
    parser.add_argument("--host", default="127.0.0.1", help="Router host")
    parser.add_argument("--port", type=int, default=5000, help="Router port")
    parser.add_argument("--nodes", type=int, default=3, help="Number of storage nodes")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    processes: list[subprocess.Popen] = []

    # Launch router
    print(f"Starting router on {args.host}:{args.port}...")
    router_cmd = [
        sys.executable,
        "router.py",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.verbose:
        router_cmd.append("--verbose")
    router_proc = subprocess.Popen(router_cmd)
    processes.append(router_proc)
    print(f"  Router PID: {router_proc.pid}")

    # Give the router a moment to start
    time.sleep(0.5)

    # Check router still alive
    if router_proc.poll() is not None:
        print("ERROR: Router process exited immediately. Check logs.")
        sys.exit(1)

    # Launch nodes
    for i in range(args.nodes):
        node_cmd = [
            sys.executable,
            "node.py",
            "--router-host", args.host,
            "--router-port", str(args.port),
            "--host", args.host,
            "--data-port", "0",  # auto-assign
            "--node-id", f"node-{i+1}",
        ]
        if args.verbose:
            node_cmd.append("--verbose")
        proc = subprocess.Popen(node_cmd)
        processes.append(proc)
        print(f"  Node node-{i+1} PID: {proc.pid}")
        time.sleep(0.3)

    print(f"\nCluster running: {len(processes)} process(es)")
    print("Press Ctrl+C to stop all processes.\n")

    try:
        # Wait for all processes
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("All processes stopped.")


if __name__ == "__main__":
    main()
