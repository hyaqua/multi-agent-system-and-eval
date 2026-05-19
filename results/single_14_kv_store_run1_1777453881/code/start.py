"""
Startup script for the distributed key-value store.

Launches the router process and a configurable number of storage node
processes, then waits for them to finish.
"""
import subprocess
import sys
import time
import signal
import argparse
import os

from protocol import DEFAULT_CLIENT_PORT, DEFAULT_NODE_PORT, DEFAULT_NODE_START_PORT


def main():
    parser = argparse.ArgumentParser(
        description="Launch the distributed KV store (router + storage nodes)"
    )
    parser.add_argument("--num-nodes", "-n", type=int, default=3,
                        help="Number of storage nodes to launch")
    parser.add_argument("--client-port", type=int, default=DEFAULT_CLIENT_PORT,
                        help="Router client port")
    parser.add_argument("--node-port", type=int, default=DEFAULT_NODE_PORT,
                        help="Router node registration port")
    parser.add_argument("--node-start-port", type=int, default=DEFAULT_NODE_START_PORT,
                        help="Starting port for storage nodes")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind all services")
    parser.add_argument("--health-interval", type=float, default=5.0,
                        help="Router health check interval")
    parser.add_argument("--health-timeout", type=float, default=2.0,
                        help="Router health check timeout")
    args = parser.parse_args()

    processes: list[subprocess.Popen] = []
    router_proc = None

    def cleanup():
        """Terminate all child processes."""
        for p in processes:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        # Give processes time to shut down
        time.sleep(0.5)
        for p in processes:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass

    def signal_handler(signum, frame):
        print(f"\n[STARTUP] Received signal {signum}, shutting down...")
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Find the directory containing our scripts
    script_dir = os.path.dirname(os.path.abspath(__file__))

    router_script = os.path.join(script_dir, "router.py")
    node_script = os.path.join(script_dir, "node.py")

    print(f"[STARTUP] Launching distributed KV store with {args.num_nodes} node(s)")
    print(f"[STARTUP] Router client port: {args.client_port}")
    print(f"[STARTUP] Router node port:  {args.node_port}")
    print()

    # 1. Launch router
    print("[STARTUP] Starting router...")
    router_proc = subprocess.Popen(
        [sys.executable, router_script,
         "--client-host", args.host,
         "--client-port", str(args.client_port),
         "--node-host", args.host,
         "--node-port", str(args.node_port),
         "--health-interval", str(args.health_interval),
         "--health-timeout", str(args.health_timeout)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    processes.append(router_proc)

    # Give the router a moment to start listening
    time.sleep(1.0)

    if router_proc.poll() is not None:
        print("[STARTUP] ERROR: Router process exited immediately!", file=sys.stderr)
        cleanup()
        sys.exit(1)

    # 2. Launch storage nodes
    for i in range(args.num_nodes):
        node_port = args.node_start_port + i
        print(f"[STARTUP] Starting storage node {i+1}/{args.num_nodes} on port {node_port}...")
        node_proc = subprocess.Popen(
            [sys.executable, node_script,
             "--host", args.host,
             "--port", str(node_port),
             "--router-host", args.host,
             "--router-port", str(args.node_port)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        processes.append(node_proc)
        # Small delay between node starts to avoid port conflicts
        time.sleep(0.3)

    print()
    print(f"[STARTUP] All processes launched. Router + {args.num_nodes} node(s) running.")
    print(f"[STARTUP] Connect with: python cli.py --host {args.host} --port {args.client_port}")
    print("[STARTUP] Press Ctrl+C to stop all processes.")
    print()

    # 3. Wait for processes to complete (or until interrupted)
    try:
        while True:
            # Check if router is still alive
            if router_proc.poll() is not None:
                print(f"[STARTUP] Router process exited with code {router_proc.returncode}")
                cleanup()
                break

            # Check if all nodes are alive
            all_dead = True
            for p in processes[1:]:  # Skip router
                if p.poll() is None:
                    all_dead = False
                    break
            if all_dead and len(processes) > 1:
                print("[STARTUP] All node processes have exited.")
                cleanup()
                break

            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        print("[STARTUP] Shutdown complete.")


if __name__ == "__main__":
    main()
