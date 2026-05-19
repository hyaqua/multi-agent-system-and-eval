# Implementation Plan: Distributed Key-Value Store in Python (Standard Library)

## 1. Files and Responsibilities

| File | Purpose |
|------|---------|
| `router.py` | Main router process. Accepts client connections, manages node registrations, consistent hash ring, health checks, logging. Routes client requests to storage nodes. |
| `node.py` | Storage node process. Maintains in-memory key-value store with TTL support. Handles commands from the router over a persistent TCP connection. |
| `client.py` | Command-line client. Connects to router, reads commands from stdin, displays responses. Supports `SET`, `GET`, `DELETE`, `LIST`. |
| `start.py` | Startup script. Launches router process and a configurable number of storage node processes using `subprocess`. |
| `protocol.py` | Defines message formats, parsing helpers, and constants (e.g., delimiters, command keywords). Keeps the wire protocol in one place. |
| `consistent_hash.py` | Consistent hashing ring implementation. Used by the router to map keys to nodes. |
| `logger.py` | (optional) Configures logging for router and nodes using the standard `logging` module. |

All code uses **only the Python standard library** (no external packages).

## 2. Architecture Overview

```
CLI client <--TCP--> Router <--TCP--> Storage Node 1
                                     Storage Node 2
                                     ...
                                     Storage Node N
```

- **Router** runs a control TCP listener for node registrations and a client TCP listener.
- Each **storage node** starts, connects to the router’s control port to register its data‑port endpoint, then listens on that data‑port for the router’s persistent command connection.
- The router manages a consistent hash ring (virtual nodes) and one long‑lived TCP connection per storage node.
- Client requests arrive at the router, are hashed, and forwarded to the responsible node. Concurrency is handled with threading and per‑node locks.
- Health checks run periodically via the same data connections (PING/PONG). Failed nodes are removed from the ring.

## 3. Implementation Order

1. **Protocol (`protocol.py`)** – Define message formats, parsing, and serialisation.
2. **Consistent Hash Ring (`consistent_hash.py`)** – Implement ring with `add_node`, `remove_node`, `get_node(key)`, virtual nodes.
3. **Storage Node (`node.py`)** – Storage logic, TTL, command handler loop.
4. **Router (`router.py`)** – Node registration, client handling, routing, health checks, logging, thread‑safety.
5. **CLI Client (`client.py`)** – Simple REPL sending requests to router.
6. **Startup Script (`start.py`)** – Launch router + N nodes with correct addresses.
7. **Integration & Testing** – Manual verification of all required features.

## 4. Libraries

Only the Python standard library:
- `socket`, `threading`, `queue`, `subprocess`, `argparse`, `hashlib`, `time`, `logging`, `uuid`, `sys`, `os`.

No `pygame` or external packages – the task explicitly requires standard library only.

## 5. Feature Implementation Details

### 1. Router listens on configurable TCP port
- `router.py` uses `argparse` to accept `--host` and `--port` (default 5000).
- Starts a `socket` listener, spawns a new thread per client connection.

### 2. Storage nodes start and register
- `node.py` accepts `--router-host`, `--router-port` (control port), `--data-port` (optional, 0 for auto).
- On startup, node binds a data socket (`data_port`) and connects to router’s control port.
- Sends `REGISTER <node_id> <host> <data_port>`; router replies `OK`.
- Node then listens on its data socket for a single persistent connection from the router.

### 3. Consistent hashing distribution
- `consistent_hash.py` uses 128 virtual nodes per physical node.
- Hash function: Python’s built‑in `hash()` (consistent within the same process; adequate for routing).
- Router calls `get_node(key)` → returns node ID of the responsible storage node.

### 4. Client SET operation
- Client sends: `SET key value [TTL]`
- Router hashes key, determines target node.
- Acquires that node’s lock, sends `SET key value [TTL]` over the persistent connection, reads response (`OK` or `ERROR`), releases lock.
- Forwards the response back to client.

### 5. Client GET operation
- Client sends: `GET key`
- Router same as above: sends `GET key` to the responsible node, returns `OK <value>` or `ERROR not found`.

### 6. Client DELETE operation
- Client sends: `DELETE key`
- Router forwards `DELETE key` to the node, propagates response.

### 7. SET with TTL (expiration)
- Node stores `{key: (value, expiry_timestamp)}` or uses `expiry = time.time() + ttl`.
- On every GET or LIST, node checks expiration: if expired, deletes the key and returns “not found” / excludes it.
- Lazy deletion is sufficient; no background cleaner needed.

### 8. Client LIST with optional prefix
- Client sends: `LIST [prefix]`
- Router **broadcasts** to all active nodes: `LIST [prefix]`.
- Collects all responses (locks each node sequentially) and merges the key lists.
- Returns a comma‑separated list of keys to the client.
- Each node filters local keys that start with the given prefix (if provided) and removes expired keys.

### 9. Router health checks & node failure
- Router runs a separate thread that every 2 seconds sends `PING` on each node’s data connection.
- Expects a `PONG` within a 1‑second timeout.
- If a node fails (timeout or connection error), router:
  1. Marks node as dead.
  2. Removes it from the hash ring (`remove_node`).
  3. Closes its connection.
  4. Logs the event.
- Redistribution happens automatically: subsequent requests for keys previously owned by the failed node now resolve to a different node (data on failed node is lost).

### 10. Simple CLI client
- `client.py` reads from stdin, sends to router, prints responses.
- Supports commands: `SET key value [TTL]`, `GET key`, `DELETE key`, `LIST [prefix]`, `QUIT`.
- Using a simple loop with `input()` and socket communication.

### 11. Text‑based protocol over TCP
- All messages are UTF‑8 newline‑delimited strings.
- Request formats:
  - `REGISTER <node_id> <host> <port>`
  - `SET <key> <value> [TTL]`
  - `GET <key>`
  - `DELETE <key>`
  - `LIST [prefix]`
  - `PING` / `PONG`
- Response: `OK` or `OK <data>` (for GET/LIST) or `ERROR <msg>`.
- `protocol.py` provides functions to parse and build these messages.

### 12. Router logging
- Router logs every client request (operation, key, target node), node registrations, failures, and redistributions.
- Uses Python `logging` with timestamps; output to stdout (or configurable file) for easy monitoring.

### 13. Concurrent clients without corruption
- **Thread safety:** The router’s hash ring and node connection map are protected by a single `threading.Lock` for ring modifications.
- Each node connection has its own `threading.Lock`; acquiring it serialises all communication on that connection.
- This guarantees that no two client threads ever interleave commands on the same node connection, preventing data corruption inside the node.
- The node itself handles one command at a time over the persistent connection, so its internal dictionary is never accessed concurrently.

### 14. Startup script
- `start.py` accepts `--nodes N` (default 3) and router parameters.
- Launches the router process first using `subprocess.Popen`.
- Then launches N node processes, each with the router’s control host/port and a unique data port (auto‑assigned).
- Prints process IDs for management.

---

**Deliverable:** A complete, runnable distributed key-value store meeting all specified requirements without external dependencies.