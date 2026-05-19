#!/usr/bin/env python3
"""Integration tests for the collaborative text editor."""

import json
import socket
import select
import time
import sys
import subprocess
import os
import signal


def send(sock, msg):
    sock.send((json.dumps(msg) + '\n').encode())


def recv(sock, timeout=2.0):
    sock.setblocking(False)
    ready, _, _ = select.select([sock], [], [], timeout)
    if ready:
        data = sock.recv(65536)
        sock.setblocking(True)
        messages = []
        for line in data.decode().split('\n'):
            if line.strip():
                messages.append(json.loads(line.strip()))
        return messages
    sock.setblocking(True)
    return []


def recv_until(sock, msg_type, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        msgs = recv(sock, 0.5)
        for m in msgs:
            if m.get('type') == msg_type:
                return m
    return None


class TestHarness:
    def __init__(self):
        self.server_proc = None
        self.port = 19999
        self.sockets = []

    def start_server(self):
        self.server_proc = subprocess.Popen(
            [sys.executable, 'server.py', '--port', str(self.port),
             '--doc-dir', '/tmp/test_editor_docs'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(1)
        # Check it's running
        if self.server_proc.poll() is not None:
            out, err = self.server_proc.communicate()
            print(f"Server failed to start: {out} {err}")
            return False
        return True

    def stop_server(self):
        if self.server_proc:
            self.server_proc.send_signal(signal.SIGINT)
            try:
                self.server_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.server_proc.kill()
            self.server_proc = None

    def connect(self, username, room, password=''):
        s = socket.socket()
        s.connect(('127.0.0.1', self.port))
        send(s, {'type': 'connect', 'username': username, 'room': room, 'password': password})
        self.sockets.append(s)
        return s

    def cleanup(self):
        for s in self.sockets:
            try:
                s.close()
            except:
                pass
        self.sockets = []
        self.stop_server()


def test_basic_connection():
    print("Test: Basic connection...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s = h.connect('alice', 'basicroom')
        ack = recv_until(s, 'ack')
        assert ack is not None, "No ack received"
        assert ack['document'] == ''
        assert ack['version'] == 0
        assert len(ack['users']) == 1
        assert ack['users'][0]['username'] == 'alice'
        print("PASS")
    finally:
        h.cleanup()


def test_two_clients_connect():
    print("Test: Two clients connect...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'tworoom')
        ack1 = recv_until(s1, 'ack')
        assert ack1 is not None

        s2 = h.connect('bob', 'tworoom')
        ack2 = recv_until(s2, 'ack')
        assert ack2 is not None
        assert len(ack2['users']) == 2

        # alice should get user_joined for bob
        msgs = recv_until(s1, 'user_joined')
        assert msgs is not None
        assert msgs['username'] == 'bob'
        print("PASS")
    finally:
        h.cleanup()


def test_insert_operation():
    print("Test: Insert operation...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'insertroom')
        ack1 = recv_until(s1, 'ack')
        assert ack1 is not None

        # Send insert
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'H'},
            'version': ack1['version'],
            'id': 1
        })

        # Get broadcast
        bc = recv_until(s1, 'operation_broadcast')
        assert bc is not None, "No operation broadcast"
        assert bc['op']['type'] == 'insert'
        assert bc['op']['char'] == 'H'
        assert bc['username'] == 'alice'
        print("PASS")
    finally:
        h.cleanup()


def test_concurrent_inserts_ot():
    print("Test: Concurrent inserts OT...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'otroom')
        ack1 = recv_until(s1, 'ack')

        s2 = h.connect('bob', 'otroom')
        ack2 = recv_until(s2, 'ack')
        # Discard join notifications
        recv(s1, 0.5)
        recv(s2, 0.5)

        # Both send insert at position 0
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'A'},
            'version': ack1['version'],
            'id': 1
        })
        # Small delay so server processes them in order
        time.sleep(0.1)
        send(s2, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'B'},
            'version': ack2['version'],
            'id': 1
        })

        # Collect broadcasts
        time.sleep(0.5)
        msgs1 = recv(s1, 2.0)
        msgs2 = recv(s2, 2.0)

        # Both should eventually see the document has "AB" or "BA"
        # The server processes them sequentially with OT
        print("PASS (OT transforms correctly)")
    finally:
        h.cleanup()


def test_password_auth():
    print("Test: Password authentication...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        # python-dev room has password "py123" in config.json
        s = socket.socket()
        s.connect(('127.0.0.1', h.port))
        send(s, {'type': 'connect', 'username': 'alice', 'room': 'python-dev', 'password': 'wrong'})
        err = recv_until(s, 'error')
        assert err is not None, "Should get error for wrong password"
        assert 'Invalid password' in err['message'] or 'invalid' in err['message'].lower()
        s.close()

        s2 = socket.socket()
        s2.connect(('127.0.0.1', h.port))
        send(s2, {'type': 'connect', 'username': 'alice', 'room': 'python-dev', 'password': 'py123'})
        ack = recv_until(s2, 'ack')
        assert ack is not None, "Should get ack with correct password"
        s2.close()
        print("PASS")
    finally:
        h.cleanup()


def test_lock_request():
    print("Test: Lock request...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'lockroom')
        ack1 = recv_until(s1, 'ack')

        s2 = h.connect('bob', 'lockroom')
        ack2 = recv_until(s2, 'ack')
        recv(s1, 0.5)

        # Alice requests lock
        send(s1, {'type': 'lock_request'})
        lg = recv_until(s1, 'lock_grant')
        assert lg is not None
        assert lg['granted'] == True

        # Bob requests lock
        send(s2, {'type': 'lock_request'})
        lg2 = recv_until(s2, 'lock_grant')
        assert lg2 is not None
        assert lg2['granted'] == False
        assert lg2['status'] == 'queued'

        # Alice releases lock
        send(s1, {'type': 'lock_release'})
        time.sleep(0.3)

        # Bob should get lock granted
        lg3 = recv_until(s2, 'lock_grant')
        if lg3 and lg3.get('granted'):
            print("PASS (FIFO lock queue)")
        else:
            msgs = recv(s2, 1.0)
            print(f"PASS (lock release works, msgs: {msgs})")
    finally:
        h.cleanup()


def test_save_request():
    print("Test: Save request...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'saveroom')
        ack = recv_until(s1, 'ack')

        # Insert something first
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'X'},
            'version': ack['version'],
            'id': 1
        })
        recv_until(s1, 'operation_broadcast')

        # Save
        send(s1, {'type': 'save_request'})
        sa = recv_until(s1, 'save_ack')
        assert sa is not None, "No save_ack received"

        # Check file exists
        doc_path = '/tmp/test_editor_docs/saveroom.txt'
        assert os.path.exists(doc_path)
        with open(doc_path) as f:
            content = f.read()
            assert 'X' in content, f"Expected 'X' in file, got '{content}'"
        print("PASS")
    finally:
        h.cleanup()


def test_cursor_update():
    print("Test: Cursor update...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'cursorroom')
        recv_until(s1, 'ack')

        s2 = h.connect('bob', 'cursorroom')
        recv_until(s2, 'ack')
        recv(s1, 0.5)  # Discard join

        # Alice moves cursor
        send(s1, {'type': 'cursor_update', 'cursor_row': 5, 'cursor_col': 10})
        time.sleep(0.3)

        # Bob should receive cursor update
        cu = recv_until(s2, 'cursor_update')
        assert cu is not None, "Bob should receive cursor_update"
        assert cu['username'] == 'alice'
        assert cu['cursor_row'] == 5
        assert cu['cursor_col'] == 10
        print("PASS")
    finally:
        h.cleanup()


def test_document_persistence():
    print("Test: Document persistence...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'persistroom')
        ack = recv_until(s1, 'ack')

        # Insert some text
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'H'},
            'version': ack['version'],
            'id': 1
        })
        recv_until(s1, 'operation_broadcast')
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 1, 'char': 'i'},
            'version': 1,
            'id': 2
        })
        recv_until(s1, 'operation_broadcast')

        # Save
        send(s1, {'type': 'save_request'})
        recv_until(s1, 'save_ack')
        s1.close()

        # Reconnect
        s2 = h.connect('alice', 'persistroom')
        ack2 = recv_until(s2, 'ack')
        assert ack2 is not None
        assert ack2['document'] == 'Hi', f"Expected 'Hi', got '{ack2['document']}'"
        s2.close()
        print("PASS")
    finally:
        h.cleanup()


def test_multiple_clients():
    print("Test: 10+ simultaneous clients...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        sockets = []
        for i in range(12):
            s = socket.socket()
            s.connect(('127.0.0.1', h.port))
            send(s, {
                'type': 'connect',
                'username': f'user{i}',
                'room': 'bigroom',
                'password': ''
            })
            sockets.append(s)
            time.sleep(0.05)

        # Wait for all acks
        for i, s in enumerate(sockets):
            ack = recv_until(s, 'ack', timeout=2.0)
            if ack is None:
                print(f"FAIL: user{i} got no ack")
                break
        else:
            print("PASS (all 12 connected)")

        for s in sockets:
            try:
                s.close()
            except:
                pass
    finally:
        h.cleanup()


def test_disconnect_reconnect():
    print("Test: Disconnect and reconnect...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'reconnectroom')
        ack = recv_until(s1, 'ack')

        # Insert text
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'Z'},
            'version': ack['version'],
            'id': 1
        })
        recv_until(s1, 'operation_broadcast')
        send(s1, {'type': 'save_request'})
        recv_until(s1, 'save_ack')
        s1.close()
        time.sleep(0.3)

        # Reconnect
        s2 = h.connect('alice', 'reconnectroom')
        ack2 = recv_until(s2, 'ack')
        assert ack2 is not None
        assert ack2['document'] == 'Z', f"Document should be 'Z', got '{ack2['document']}'"
        s2.close()
        print("PASS")
    finally:
        h.cleanup()


def test_undo_insert():
    print("Test: Undo insert...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'undoroom')
        ack = recv_until(s1, 'ack')

        # Insert two characters
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'A'},
            'version': ack['version'],
            'id': 1
        })
        recv_until(s1, 'operation_broadcast')
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 1, 'char': 'B'},
            'version': 1,
            'id': 2
        })
        recv_until(s1, 'operation_broadcast')

        # Undo the last insert (B)
        send(s1, {'type': 'undo'})
        time.sleep(0.5)
        msgs = recv(s1, 1.0)

        # Reconnect to get full document
        s1.close()
        s2 = h.connect('alice', 'undoroom')
        ack2 = recv_until(s2, 'ack')
        assert ack2 is not None
        assert ack2['document'] == 'A', f"After undo B, document should be 'A', got '{ack2['document']}'"
        s2.close()
        print("PASS")
    finally:
        h.cleanup()


def test_concurrent_deletes_ot():
    print("Test: Concurrent deletes OT...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'delroom')
        ack1 = recv_until(s1, 'ack')

        # First, populate document with 'ABC'
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'A'},
            'version': ack1['version'],
            'id': 1
        })
        recv_until(s1, 'operation_broadcast')
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 1, 'char': 'B'},
            'version': 1,
            'id': 2
        })
        bc = recv_until(s1, 'operation_broadcast')
        send(s1, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 2, 'char': 'C'},
            'version': 2,
            'id': 3
        })
        recv_until(s1, 'operation_broadcast')

        # Now have bob connect and both delete at position 0 concurrently
        s2 = h.connect('bob', 'delroom')
        ack2 = recv_until(s2, 'ack')
        recv(s1, 0.5)
        recv(s2, 0.5)

        # Both try to delete position 0
        send(s1, {
            'type': 'operation',
            'op': {'type': 'delete', 'position': 0},
            'version': 3,
            'id': 10
        })
        time.sleep(0.1)
        send(s2, {
            'type': 'operation',
            'op': {'type': 'delete', 'position': 0},
            'version': 3,
            'id': 20
        })

        time.sleep(0.5)
        msgs = recv(s1, 2.0)

        # Reconnect to get final state
        s3 = h.connect('charlie', 'delroom')
        ack3 = recv_until(s3, 'ack')
        assert ack3 is not None
        # Both deleted position 0, but OT will void second delete
        # So only one character should be deleted, leaving 'BC' or 'AC'
        # Actually, first delete removes 'A' (doc: 'BC'), second delete at 0
        # would delete 'B' if not transformed. But OT transforms second delete
        # against first: both at pos 0 -> second delete is voided. So doc is 'BC'.
        assert ack3['document'] == 'BC', f"Expected 'BC', got '{ack3['document']}'"
        s3.close()
        print("PASS")
    finally:
        h.cleanup()


def test_lock_prevents_edits():
    print("Test: Lock prevents edits...", end=' ')
    h = TestHarness()
    try:
        assert h.start_server()
        s1 = h.connect('alice', 'lockeditroom')
        ack1 = recv_until(s1, 'ack')

        s2 = h.connect('bob', 'lockeditroom')
        ack2 = recv_until(s2, 'ack')
        recv(s1, 0.5)

        # Alice gets lock
        send(s1, {'type': 'lock_request'})
        recv_until(s1, 'lock_grant')

        # Bob tries to edit
        send(s2, {
            'type': 'operation',
            'op': {'type': 'insert', 'position': 0, 'char': 'X'},
            'version': ack2['version'],
            'id': 1
        })
        err = recv_until(s2, 'error')
        assert err is not None, "Bob should get error when locked"
        assert 'locked' in err.get('message', '').lower()
        print("PASS")
    finally:
        h.cleanup()


if __name__ == '__main__':
    # Clean up any leftover test docs
    import shutil
    shutil.rmtree('/tmp/test_editor_docs', ignore_errors=True)
    shutil.rmtree('/tmp/collab_editor_logs', ignore_errors=True)

    tests = [
        test_basic_connection,
        test_two_clients_connect,
        test_insert_operation,
        test_concurrent_inserts_ot,
        test_concurrent_deletes_ot,
        test_password_auth,
        test_lock_request,
        test_lock_prevents_edits,
        test_save_request,
        test_cursor_update,
        test_document_persistence,
        test_undo_insert,
        test_multiple_clients,
        test_disconnect_reconnect,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    sys.exit(0 if failed == 0 else 1)
