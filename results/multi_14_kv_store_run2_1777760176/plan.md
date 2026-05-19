# Implementation Plan: Distributed Key-Value Store

## 1. Overview
A single-machine distributed key-value store built with Python’s standard library.  
Multiple storage node processes register with a central router process.  
The router uses **consistent hashing** to distribute keys among nodes.  
Clients connect to the router via TCP and issue text-based CRUD commands.  
The system supports TTL-based expiration, node failure detection, and redistribution.

## 2. Architecture

```
                 ┌─────────────────┐
                 │   Client CLI    │
                 └────────┬────────┘
                          │ TCP (text protocol)
                 ┌────────▼────────┐
                 │     Router      │  ← TCP server + client pool
                 │ manages ring    │
                 │ health checks   │
                 └───┬──────────┬──┘
                     │ TCP cmds │ TCP cmds
         ┌───────────▼──┐    ┌──▼─────────────┐
         │  Node 1      │    │  Node 2 ... N  │
         │ stores keys  │    │  stores keys   │
         │ (+ expiration)│    │  (+ expiration)│
         └──────────────┘    └────────────────┘
```

- **Router**  
  - Accepts client connections on a configurable port.  
  - Maintains a consistent hash ring that maps keys to storage nodes.  
  - Forwards requests to the appropriate node via TCP.  
  - Periodically health‑checks nodes; removes unresponsive ones and redistributes their key ranges.  
  - Logs all operations and status changes.

- **Storage Node**  
  - Starts, opens a TCP server on a random port, and registers with the router.  
  - Stores key‑value pairs in a dictionary with optional TTL.  
  - Handles `SET`, `GET`, `DELETE`, and `LIST` commands from the router.  
  - Expired keys are rejected on access (no background cleaner required, but optionally a thread can sweep).

- **Client CLI**  
  - Interactive script that reads user commands and sends them to the router over TCP.

## 3. Modules and Files

| File | Purpose |
|------|---------|
| `router.py` | Main router process: server for clients, consistent hashing ring, node management, health checker, command forwarding. |
| `node.py` | Storage node process: starts server, registers with router, handles key‑value operations with TTL. |
| `client.py` | CLI client: interactive loop to send commands to router. |
| `hash_ring.py` | Consistent hashing ring implementation (add/remove nodes, route key). |
| `protocol.py` | Shared constants, message formats, and simple text‑protocol parsing/serialisation. |
| `startup.py` | Launcher script that starts the router and a configurable number of nodes. |

## 4. Data Flow

1. **Startup**  
   - `startup.py` spawns `router.py` (given a port).  
   - Then spawns `node.py` instances, each with the router’s address.  
   - Each node starts its own TCP server, connects to the router, and sends `REGISTER <port>`.

2. **Registration**  
   - Router receives `REGISTER`, notes the node’s host (localhost) and port.  
   - Inserts the node (with multiple virtual nodes) into the consistent hash ring.  
   - Replies with `OK` to the node.

3. **Client Request**  
   - Client connects to router, sends a line‑terminated text command (`SET key value [TTL]`, `GET key`, `DELETE key`, `LIST [prefix]`).  
   - Router receives command, validates, logs it.  
   - If command is `SET`, `GET`, `DELETE`: router hashes the key, finds the owning node via the ring.  
   - If `LIST` (with optional prefix): sends `LIST <prefix>` to **all** active nodes, collects results, returns aggregated list.  
   - Router opens a TCP connection to the target node, forwards the command, reads response, closes connection (except maybe keep‑alive for health).  
   - Router converts node response into a client‑friendly reply (`OK`, `VALUE v`, etc.) and sends it back.

4. **Health Check & Failure Detection**  
   - Router runs a periodic thread that tries to connect to each known node or sends a `PING` command.  
   - If a node does not respond (connection refused, timeout), it is marked as **failed**.  
   - Router removes the failed node from the hash ring. Future requests for keys previously owned by that node will be routed to the next node clockwise (automatic redistribution).  
   - A log entry is emitted.

5. **TTL Expiration**  
   - On `SET` with TTL, node stores `expiry_time = now + ttl`.  
   - On `GET`, node checks if current time > expiry_time; if so, returns `NOT_FOUND` and deletes the entry.  
   - `DELETE` always works; `LIST` ignores expired keys (or optionally includes them but marks as expired – we ignore them for simplicity).

## 5. Implementation Order

1. **`protocol.py`** – Define command/response formats, functions to parse and serialise messages.  
2. **`hash_ring.py`** – Implement consistent hashing: `add_node`, `remove_node`, `get_node` for a key.  
3. **`node.py`** – Implement the storage server:
   - Start TCP server on a random port.
   - Connect to router, send `REGISTER <port>`.
   - Handle incoming commands in a loop (handle one connection at a time with threads).  
4. **`router.py`** – Build the router:
   - TCP server for clients.
   - On startup, start health‑check thread.
   - Accept node registrations, maintain ring.
   - Forward commands to nodes.
   - Aggregate LIST responses.
   - Logging.
5. **`client.py`** – Simple REPL that sends commands to router and prints responses.  
6. **`startup.py`** – Use `subprocess.Popen` to launch router, then nodes with configurable count.  
7. **Integration test & polish** – Manual test using the CLI, verify TTL, failure detection, redistribution.

## 6. Required Feature Details

### Router listening on configurable port
- `router.py` takes port as command‑line argument or environment variable.  
- Uses `socket.create_server` and `threading` to accept multiple client connections.

### Storage node registration
- `node.py` takes router’s address (`host:port`) as argument.  
- Creates its own TCP server on port `0` (OS assigns free port).  
- Connects to router, sends `REGISTER <allocated_port>` over a fresh TCP connection, waits for `OK`.  
- Router stores node: `id → (host, port)`, adds virtual nodes to ring.

### Consistent key distribution
- Virtual nodes: each physical node gets **128** virtual nodes by default (configurable).  
- `hash_ring.py` uses `hashlib.md5(key.encode()).digest()` and maps to integer for ring position.  
- Ring kept sorted; `bisect` module used to find the first virtual node whose hash is ≥ key hash, wrapping around.

### SET
- Client sends `SET <key> <value> [TTL]`.  
- Router hashes key, finds node.  
- Router opens TCP to node, sends `SET key value [TTL]`.  
- Node stores key with `expiry = now + ttl` if TTL given, else `None`.  
- Node replies `OK`, router forwards `OK` to client.

### GET
- Client `GET <key>`. Router routes, node checks expiry.  
- On success: `VALUE <value>`; on not found/expired: `NOT_FOUND`.

### DELETE
- Client `DELETE <key>`. Router routes, node deletes if exists, replies `OK` or `NOT_FOUND`.

### SET with TTL
- Node stores `(value, expiry)` tuple.  
- During `GET`, if `expiry` is set and `time.time() > expiry`, it’s treated as not found and entry removed.  
- No background cleanup required, but optional lazy cleanup on GET keeps memory in check.

### LIST with prefix
- Client `LIST [prefix]`. Router sends `LIST prefix` to all active nodes.  
- Each node scans its dictionary, collects keys that start with prefix (and are not expired).  
- Node returns keys separated by newlines or a special delimiter.  
- Router collects all keys, deduplicates (should not exist across nodes), and returns sorted list to client.

### Node failure detection
- Health thread in router: every **2 seconds** iterates over all registered nodes.  
- For each node, open a TCP connection with a short timeout (1 second), send `PING`, expect `PONG`.  
- If connection fails or response not received, mark node as down.  
- **Remove** the node from the ring (all its virtual nodes).  
- Log the event. If the node later reconnects, it must re‑register (but for simplicity we don’t handle revival automatically).

### Key range redistribution
- When a node is removed from the ring, any future request for a key previously owned by it will now be routed to the next virtual node clockwise (i.e., the successor on the ring).  
- This happens automatically because the ring is updated; no explicit data migration is attempted (data on failed node is lost).  
- The router logs which node took over the range.

### CLI client
- `client.py` connects to router’s address (given as argument).  
- Interactive prompt `>`. Supports commands: `SET key val [ttl]`, `GET key`, `DELETE key`, `LIST [prefix]`, `QUIT`.  
- Sends line to router, reads response, prints.

### Text-based protocol
- All messages are UTF‑8 encoded lines terminated by `\n`.  
- Request format: `COMMAND arg1 arg2 ...`.  
- Response lines: `OK`, `VALUE <val>`, `NOT_FOUND`, `LIST <key1>\n<key2>...` (keys separated by newline, with “LIST” header), `ERROR <message>`.

### Logging
- Router uses `logging` module to output to stdout and/or file.  
- Logs connection events, commands received, nodes added/removed, forwarding actions, and failures.

### Concurrency
- Router uses one thread per client connection (thread pool can be basic `threading.Thread`).  
- To protect shared state (ring, node registry), a `threading.Lock` is used.  
- Nodes handle one connection at a time but can use threads to accept multiple simultaneous commands from router (though typically sequential on same connection if persistent, but we use short‑lived connections so each command from router is a separate connection; node’s server loop can handle them with a new thread per connection to avoid blocking).  
- Since only router talks to nodes, no contention from multiple clients on the same key across nodes because only the router initiates node connections; still, node’s dictionary access is protected by a lock.

### Startup script
- `startup.py` accepts `--router-port`, `--num-nodes`, and optionally `--virtual-nodes-per-node`.  
- Spawns router process (detached).  
- Waits a short time, then spawns node processes (each as a separate process) with the router’s address.  
- Prints all process IDs for management.

## 7. Libraries
- **Standard library only**: `socket`, `threading`, `subprocess`, `time`, `hashlib`, `bisect`, `logging`, `sys`, `os`, `argparse`, `random` (for port selection if needed – but `0` suffices).

## 8. Notes
- Persistent TCP connections between router and nodes could optionally be kept open for efficiency, but the short‑lived approach simplifies implementation and still meets requirements.  
- The ring uses virtual nodes to achieve better key distribution; number can be tuned.  
- TTL cleanup is lazy (on access). A separate sweeper thread inside the node could run periodically, but not required for functionality.  
- The system does not handle network partition or Byzantine failures; node failure is detected purely by TCP connect/response timeout.  
- The plan assumes all processes run on localhost for registration and communication.