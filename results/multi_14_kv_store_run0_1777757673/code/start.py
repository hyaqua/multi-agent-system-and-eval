"""
Startup script that launches the router and a configurable number of
storage node processes using subprocess.

Usage:
    python start.py --num-nodes 3
    python start.py --num-nodes 5 --client-port 5555 --node-port 5556
"""

import argparse
import subprocess
import sys
import time
import signal
import os


def main():
    parser = argparse.ArgumentParser(
        description="Start the distributed KV store")
    parser.add_argument("--num-nodes", type=int, default=3,
                        help="Number of storage nodes to start")
    parser.add_argument("--client-port", type=int, default=5555,
                        help="Router client port")
    parser.add_argument("--node-port", type=int, default=5556,
                        help="Router node port")
    parser.add_argument("--health-interval", type=float, default=2.0,
                        help="Health check interval")
    parser.add_argument("--health-timeout", type=float, default=1.0,
                        help="Health check timeout")
    parser.add_argument("--vcount", type=int, default=100,
                        help="Virtual nodes per storage node")
    args = parser.parse_args()

    processes: list[subprocess.Popen] = []

    def cleanup():
        """Terminate all child processes."""
        print("\nShutting down...")
        for p in processes:
            try:
                p.terminate()
            except OSError:
                pass
        # Wait briefly for graceful shutdown
        time.sleep(0.5)
        for p in processes:
            try:
                p.kill()
                p.wait()
            except OSError:
                pass
        print("All processes stopped.")

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda sig, frame: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: cleanup() or sys.exit(0))

    # Build the python command (use same interpreter)
    python_exe = sys.executable

    # Determine script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Launch router
    router_script = os.path.join(script_dir, "router.py")
    router_args = [
        python_exe, router_script,
        "--client-port", str(args.client_port),
        "--node-port", str(args.node_port),
        "--health-interval", str(args.health_interval),
        "--health-timeout", str(args.health_timeout),
    ]
    print(f"Starting router: {' '.join(router_args)}")
    router_proc = subprocess.Popen(router_args, stdout=sys.stdout, stderr=sys.stderr)
    processes.append(router_proc)

    # Give router time to bind its ports
    print("Waiting for router to initialise...")
    time.sleep(1.5)

    # Launch storage nodes
    node_script = os.path.join(script_dir, "storage_node.py")
    for i in range(args.num_nodes):
        node_id = f"node-{i}"
        node_args = [
            python_exe, node_script,
            "--id", node_id,
            "--router-host", "localhost",
            "--router-port", str(args.node_port),
            "--vcount", str(args.vcount),
        ]
        print(f"Starting storage node {node_id}")
        node_proc = subprocess.Popen(node_args, stdout=sys.stdout, stderr=sys.stderr)
        processes.append(node_proc)
        time.sleep(0.3)  # stagger startups

    print(f"\nAll processes started. {args.num_nodes} nodes + 1 router.")
    print(f"Clients can connect on port {args.client_port}.")
    print("Press Ctrl+C to stop.\n")

    # Monitor processes
    try:
        while True:
            time.sleep(1)
            # Check if router is still alive
            if router_proc.poll() is not None:
                print("Router process died. Shutting down.")
                cleanup()
                sys.exit(1)
            # Check nodes
            for i, p in enumerate(processes[1:], start=0):
                if p.poll() is not None:
                    print(f"Node node-{i} died.")
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
