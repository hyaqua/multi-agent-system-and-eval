"""Startup script that launches the router and a configurable number of
storage nodes on a single machine.

Usage: python start.py [num_nodes] [router_port] [node_start_port]
"""

import subprocess
import sys
import time
import signal


def main():
    num_nodes = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    router_port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
    node_start_port = int(sys.argv[3]) if len(sys.argv) > 3 else 9001
    host = "127.0.0.1"

    processes: list[subprocess.Popen] = []

    def cleanup():
        print("\nShutting down all processes...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(0.5)
        for p in processes:
            try:
                p.kill()
            except Exception:
                pass

    def sig_handler(signum, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # ------------------------------------------------------------------
    # 1. Launch router
    # ------------------------------------------------------------------
    print(f"Starting router on {host}:{router_port} ...")
    router_proc = subprocess.Popen(
        [sys.executable, "-u", "router.py", host, str(router_port)],
        stdout=sys.stdout, stderr=sys.stderr
    )
    processes.append(router_proc)
    time.sleep(0.5)

    if router_proc.poll() is not None:
        print("ERROR: Router failed to start!")
        cleanup()
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Launch storage nodes
    # ------------------------------------------------------------------
    for i in range(num_nodes):
        node_id = f"node-{i + 1}"
        node_port = node_start_port + i
        print(f"Starting {node_id} on {host}:{node_port} ...")
        proc = subprocess.Popen(
            [sys.executable, "-u", "node.py", node_id, host,
             str(node_port), host, str(router_port)],
            stdout=sys.stdout, stderr=sys.stderr
        )
        processes.append(proc)
        time.sleep(0.3)

    print(f"\nAll {1 + num_nodes} processes launched.")
    print(f"Router : {host}:{router_port}")
    for i in range(num_nodes):
        print(f"  Node  : {host}:{node_start_port + i}  (node-{i+1})")
    print("\nPress Ctrl-C to stop.\n")

    # ------------------------------------------------------------------
    # 3. Wait
    # ------------------------------------------------------------------
    try:
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"[!] Process exited with code {p.returncode}")
                    cleanup()
                    sys.exit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
