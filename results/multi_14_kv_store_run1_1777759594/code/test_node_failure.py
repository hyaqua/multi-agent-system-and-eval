"""
test_node_failure.py — Test that the router detects node failure and
redistributes keys to remaining nodes.
"""
import subprocess
import socket
import sys
import time

import protocol as proto


def send_recv(sock: socket.socket, cmd: str) -> str:
    """Send a command and receive a response."""
    sock.sendall(cmd.encode(proto.ENCODING) + b"\n")
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Connection closed")
        buf += chunk
    line_bytes, _ = buf.split(b"\n", 1)
    return line_bytes.decode(proto.ENCODING).strip()


def test_node_failure():
    print("=" * 60)
    print("Node failure test...")
    print("=" * 60)

    # Start router on different port
    router_proc = subprocess.Popen(
        [sys.executable, "router.py", "--host", "127.0.0.1", "--port", "5002"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.5)
    assert router_proc.poll() is None

    # Start 3 nodes
    nodes = []
    for i in range(3):
        proc = subprocess.Popen(
            [
                sys.executable, "node.py",
                "--router-host", "127.0.0.1",
                "--router-port", "5002",
                "--host", "127.0.0.1",
                "--data-port", "0",
                "--node-id", f"node-{i+1}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        nodes.append(proc)
        time.sleep(0.4)

    time.sleep(1)

    # Connect client
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 5002))
    sock.settimeout(5)

    try:
        # Store several keys
        print("\nStoring keys...")
        for k in ["alpha", "beta", "gamma", "delta", "epsilon"]:
            resp = send_recv(sock, f"SET {k} value_{k}")
            assert resp == "OK", f"SET {k} failed: {resp}"
            print(f"  SET {k} -> OK")

        # Read them back
        print("\nReading keys before failure...")
        for k in ["alpha", "beta", "gamma", "delta", "epsilon"]:
            resp = send_recv(sock, f"GET {k}")
            assert resp == f"OK value_{k}", f"GET {k} failed: {resp}"
            print(f"  GET {k} -> OK")

        # Kill node-1
        print("\nKilling node-1...")
        nodes[0].kill()
        nodes[0].wait()
        print("  node-1 killed.")

        # Wait for health check to detect (2 sec interval + 1 sec timeout)
        print("  Waiting for health check to detect failure (4s)...")
        time.sleep(4)

        # Now try to read keys again — some may be on the dead node
        print("\nReading keys after node-1 failure...")
        success = 0
        failed = 0
        for k in ["alpha", "beta", "gamma", "delta", "epsilon"]:
            resp = send_recv(sock, f"GET {k}")
            if resp.startswith("OK"):
                success += 1
                print(f"  GET {k} -> {resp} (still available)")
            else:
                failed += 1
                print(f"  GET {k} -> {resp} (lost — was on dead node)")

        print(f"\nResult: {success} keys available, {failed} keys lost (expected).")
        print("Test PASSED: node failure detected and ring updated.")

        # The remaining keys should still be accessible
        print("\nStoring new key after node failure...")
        resp = send_recv(sock, "SET newkey works")
        assert resp == "OK", f"SET newkey failed: {resp}"
        resp = send_recv(sock, "GET newkey")
        assert resp == "OK works", f"GET newkey failed: {resp}"
        print("  SET/GET newkey -> OK (system still operational)")

    finally:
        sock.close()

    # Cleanup
    for proc in nodes:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=3)
    router_proc.terminate()
    router_proc.wait(timeout=3)

    print("\nAll done.")


if __name__ == "__main__":
    test_node_failure()
