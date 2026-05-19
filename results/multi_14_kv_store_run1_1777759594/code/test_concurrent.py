"""
test_concurrent.py — Test multiple concurrent clients accessing the store.
"""
import subprocess
import socket
import sys
import time
import threading

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


def client_worker(thread_id: int, results: list, barrier: threading.Barrier):
    """Each worker connects independently and does SET/GET operations."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 5003))
    sock.settimeout(5)
    try:
        # Wait for all threads to be ready
        barrier.wait()

        for i in range(20):
            key = f"t{thread_id}_key{i}"
            val = f"val_{thread_id}_{i}"
            resp = send_recv(sock, f"SET {key} {val}")
            if resp != "OK":
                results.append(f"FAIL SET {key}: {resp}")
                return
            resp = send_recv(sock, f"GET {key}")
            if resp != f"OK {val}":
                results.append(f"FAIL GET {key}: expected OK {val}, got {resp}")
                return
        results.append(f"Thread {thread_id}: all 20 keys OK")
    except Exception as e:
        results.append(f"Thread {thread_id} ERROR: {e}")
    finally:
        sock.close()


def test_concurrent():
    print("=" * 60)
    print("Concurrent clients test...")
    print("=" * 60)

    router_proc = subprocess.Popen(
        [sys.executable, "router.py", "--host", "127.0.0.1", "--port", "5003"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.5)
    assert router_proc.poll() is None

    # Start 2 nodes
    nodes = []
    for i in range(2):
        proc = subprocess.Popen(
            [
                sys.executable, "node.py",
                "--router-host", "127.0.0.1",
                "--router-port", "5003",
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

    # Launch 5 concurrent client threads
    results: list[str] = []
    barrier = threading.Barrier(5)
    threads = []
    for tid in range(5):
        t = threading.Thread(target=client_worker, args=(tid, results, barrier))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\nResults:")
    all_ok = True
    for r in results:
        print(f"  {r}")
        if not r.startswith("Thread") or "ERROR" in r:
            all_ok = False

    if all_ok:
        print("\nALL CONCURRENT TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")

    # Cleanup
    for proc in nodes:
        proc.terminate()
        proc.wait(timeout=3)
    router_proc.terminate()
    router_proc.wait(timeout=3)


if __name__ == "__main__":
    test_concurrent()
