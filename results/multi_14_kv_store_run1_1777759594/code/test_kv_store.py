"""
test_kv_store.py — Integration test for the distributed key-value store.

Starts router and nodes, then runs a series of commands against the
router and verifies expected responses.
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


def test_all():
    print("=" * 60)
    print("Starting integration test...")
    print("=" * 60)

    # Start router
    print("\n[1] Starting router...")
    router_proc = subprocess.Popen(
        [sys.executable, "router.py", "--host", "127.0.0.1", "--port", "5001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.5)
    assert router_proc.poll() is None, "Router failed to start"
    print("  Router started (PID: %s)" % router_proc.pid)

    # Start 3 nodes
    nodes = []
    for i in range(3):
        print(f"\n[2.{i+1}] Starting node node-{i+1}...")
        proc = subprocess.Popen(
            [
                sys.executable, "node.py",
                "--router-host", "127.0.0.1",
                "--router-port", "5001",
                "--host", "127.0.0.1",
                "--data-port", "0",
                "--node-id", f"node-{i+1}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        nodes.append(proc)
        time.sleep(0.5)
        assert proc.poll() is None, f"Node node-{i+1} failed to start"
        print(f"  Node node-{i+1} started (PID: {proc.pid})")

    # Give everything time to stabilise
    time.sleep(1)

    # Connect client
    print("\n[3] Connecting test client to router...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 5001))
    sock.settimeout(5)
    print("  Connected.")

    try:
        # ---- SET operations ----
        print("\n[4] Testing SET...")
        resp = send_recv(sock, "SET name Alice")
        assert resp == "OK", f"SET name Alice failed: {resp}"
        print("  SET name Alice -> OK")

        resp = send_recv(sock, "SET city NewYork")
        assert resp == "OK", f"SET city NewYork failed: {resp}"
        print("  SET city NewYork -> OK")

        resp = send_recv(sock, "SET country USA")
        assert resp == "OK", f"SET country USA failed: {resp}"
        print("  SET country USA -> OK")

        # ---- GET operations ----
        print("\n[5] Testing GET...")
        resp = send_recv(sock, "GET name")
        assert resp == "OK Alice", f"GET name failed: {resp}"
        print(f"  GET name -> {resp}")

        resp = send_recv(sock, "GET city")
        assert resp == "OK NewYork", f"GET city failed: {resp}"
        print(f"  GET city -> {resp}")

        resp = send_recv(sock, "GET nonexistent")
        assert resp.startswith("ERROR"), f"GET nonexistent should error: {resp}"
        print(f"  GET nonexistent -> {resp}")

        # ---- SET with TTL ----
        print("\n[6] Testing SET with TTL...")
        resp = send_recv(sock, "SET tempval hello 2")
        assert resp == "OK", f"SET tempval failed: {resp}"
        print("  SET tempval hello 2 -> OK")

        resp = send_recv(sock, "GET tempval")
        assert resp == "OK hello", f"GET tempval (before expiry) failed: {resp}"
        print(f"  GET tempval (before expiry) -> {resp}")

        print("  Waiting 3 seconds for TTL expiry...")
        time.sleep(3)

        resp = send_recv(sock, "GET tempval")
        assert resp.startswith("ERROR"), f"GET tempval (after expiry) should error: {resp}"
        print(f"  GET tempval (after expiry) -> {resp}")

        # ---- DELETE ----
        print("\n[7] Testing DELETE...")
        resp = send_recv(sock, "DELETE city")
        assert resp == "OK", f"DELETE city failed: {resp}"
        print("  DELETE city -> OK")

        resp = send_recv(sock, "GET city")
        assert resp.startswith("ERROR"), f"GET city after delete should error: {resp}"
        print(f"  GET city (after delete) -> {resp}")

        # ---- LIST ----
        print("\n[8] Testing LIST...")
        resp = send_recv(sock, "LIST")
        assert resp.startswith("OK"), f"LIST failed: {resp}"
        keys = resp[3:].split(",") if resp[3:] else []
        print(f"  LIST -> {sorted(keys)}")
        assert "name" in keys, "LIST should contain 'name'"
        assert "country" in keys, "LIST should contain 'country'"
        assert "city" not in keys, "LIST should NOT contain 'city' (deleted)"
        assert "tempval" not in keys, "LIST should NOT contain 'tempval' (expired)"

        # ---- LIST with prefix ----
        print("\n[9] Testing LIST with prefix...")
        resp = send_recv(sock, "SET pref_abc 1")
        resp = send_recv(sock, "SET pref_xyz 2")
        resp = send_recv(sock, "LIST pref_")
        assert resp.startswith("OK"), f"LIST pref_ failed: {resp}"
        pref_keys = resp[3:].split(",") if resp[3:] else []
        print(f"  LIST pref_ -> {sorted(pref_keys)}")
        assert all(k.startswith("pref_") for k in pref_keys), "All keys should start with pref_"

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    finally:
        sock.close()

    # Cleanup
    print("\n[10] Cleaning up...")
    for proc in nodes:
        proc.terminate()
        proc.wait(timeout=3)
    router_proc.terminate()
    router_proc.wait(timeout=3)
    print("  Done.")


if __name__ == "__main__":
    test_all()
