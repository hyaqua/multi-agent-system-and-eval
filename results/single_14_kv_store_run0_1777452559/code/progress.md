STATUS: COMPLETE

## Implemented Features

### 1. Router process with configurable TCP port ✅
- `router.py` listens on a configurable host:port for client connections and node registrations.
- Uses threading to handle multiple concurrent client connections.
- Server socket has a 1-second timeout so the accept loop can check the `running` flag for graceful shutdown.

### 2. Multiple storage node processes with registration ✅
- `node.py` starts, binds to its own host:port, and registers with the router by sending `REGISTER <node_id> <host> <port>`.
- Router responds `REGISTERED` and adds the node to its hash ring.
- Configurable number of nodes (default 3) via `start.py`.

### 3. Consistent hashing for key distribution ✅
- Uses MD5 hash of keys and node IDs to place them on a 128-bit ring.
- Binary search (bisect) finds the responsible node for each key.
- Ring is rebuilt whenever nodes join or leave.

### 4. SET operation ✅
- Client sends `SET <key> <value> [<ttl_seconds>]`.
- Router hashes the key, finds the responsible node, and forwards the request.
- Node stores the value in an in-memory dict with optional expiry timestamp.

### 5. GET operation ✅
- Client sends `GET <key>`.
- Router routes to the correct node, which returns `VALUE <value>` or `NOT_FOUND`.
- Expired keys are cleaned up on access.

### 6. DELETE operation ✅
- Client sends `DELETE <key>`.
- Returns `DELETED` if key existed, `NOT_FOUND` otherwise.

### 7. TTL-based expiration ✅
- SET supports an optional TTL in seconds as a trailing integer.
- Keys are stored with an expiry timestamp.
- Expired keys are lazily cleaned up on GET, and also purged during LIST.
- Tested: key with 1s TTL returns NOT_FOUND after expiry.

### 8. LIST with prefix filtering ✅
- Client sends `LIST [<prefix>]`.
- Router fans out to ALL alive nodes, collects matching keys, sorts, and returns them.
- Prefix filtering uses `str.startswith()`.
- Multi-line protocol: `LIST_BEGIN <count>` followed by keys, terminated by `LIST_END`.

### 9. Health checks and node failure detection ✅
- Router runs a background thread that pings every node every 5 seconds.
- Nodes respond with `PONG`.
- If a node fails to respond within 2 seconds, it is marked as unresponsive.
- The ring is rebuilt, redistributing the failed node's key range to remaining nodes.
- Tested: killed a node, router detected it, subsequent requests succeed on remaining nodes.

### 10. Key range redistribution on node failure ✅
- When a node is marked unresponsive, `_rebuild_ring()` is called.
- The consistent hashing ring is recalculated with only alive nodes.
- New keys in the failed node's range now map to other nodes.
- Note: Without replication, data on the failed node is lost (keys return NOT_FOUND from new owners).

### 11. CLI client ✅
- `client.py` provides an interactive prompt.
- Supports SET, GET, DELETE, LIST, QUIT commands.
- Handles multi-line LIST responses.

### 12. Text-based protocol over TCP ✅
- All messages are newline-terminated UTF-8 strings.
- Multi-line responses use `LIST_BEGIN <count>` / `LIST_END` framing.
- `BufferedSocket` class ensures reliable line-oriented reads.

### 13. Router logging ✅
- All operations logged with key, target node, and result.
- Node registrations, failures, and recoveries are logged.
- Format: `[LOG] <operation> → node <id>  (<result>)`.

### 14. Concurrent client support ✅
- Each client connection is handled in a separate thread.
- Node store is protected by a `threading.Lock` for thread-safe access.
- Tested with two simultaneous clients writing and reading concurrently without issues.

### 15. Startup script ✅
- `start.py` launches the router and a configurable number of node processes.
- Usage: `python start.py [num_nodes] [router_port] [node_start_port]`.
- Uses `subprocess.Popen` with `-u` flag for unbuffered output.
- Clean shutdown on Ctrl-C (SIGINT/SIGTERM).

## Files

| File | Purpose |
|------|---------|
| `common.py` | Hash function, `BufferedSocket` for line-oriented TCP |
| `router.py` | Router process: consistent hashing ring, client routing, health checks |
| `node.py` | Storage node process: in-memory KV store with TTL |
| `client.py` | Interactive CLI client |
| `start.py` | Startup script to launch router + N nodes |

## How to Run

```bash
# Start the system (router + 3 nodes)
python start.py 3 9000 9001

# In another terminal, use the CLI client
python client.py 127.0.0.1 9000
```

## Test Results

- Basic SET/GET: ✅
- DELETE: ✅
- TTL expiry (1s, 2s): ✅
- LIST with prefix filtering: ✅
- LIST all keys: ✅
- Key distribution across 3 nodes: ✅
- Concurrent clients (2 simultaneous): ✅
- Node failure detection (health check): ✅
- Operation after node failure (redistribution): ✅
- DELETE non-existent key: ✅
- Startup script: ✅
