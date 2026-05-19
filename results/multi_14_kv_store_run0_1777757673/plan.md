# Revised Implementation Plan: Distributed Key‑Value Store

This plan refines the original design to fix the three critical issues identified by the review:

1. **SET with spaces in values** – router’s handler used a naive `split()` that truncated values.
2. **LIST response corruption** – router expected an `END`-terminated list while nodes now return a count‑based format, causing a mismatch.
3. **Startup script argument bug** – `start.py` did not pass the required `--id` to storage nodes.

**Root Cause of Unapplied Fixes:**  
The previously proposed protocol improvements (`parse_set`, `encode_set`, `recv_counted_lines`) were placed in `protocol.py` but never imported by `router.py`, `client.py`, or `storage_node.py`. Furthermore, a duplicate `protocol.py` existed, and the start script still lacked the `--id` argument in the actual executed code. This revision ensures all components integrate the new protocol, duplicates are removed, and the startup script works correctly.

All other features (consistent hashing, concurrency, health checks, TTL, etc.) remain unchanged.

---

## Protocol Finalisation

The communication protocol remains line‑oriented (`\n` terminated). The following rules apply to all messages.

### SET command (with optional quoting)

```
SET key value [ttl]\n
```

- `key` is a single token (no spaces).
- `value` is the complete value string. If it contains spaces, the entire value **must** be enclosed in double‑quotes. Inside quotes, a literal `"` must be escaped as `\"`.  
  *Example:*  `SET mykey "hello world" 3600`
- `ttl` (optional) is an integer number of seconds. When absent, TTL defaults to 0 (no expiration).
- If `ttl` is provided and the value is quoted, the closing quote must appear before the TTL token.

**Parsing rules (used by router key extraction and storage nodes):**

- After the `SET` keyword, the key is obtained by splitting on whitespace (`line.split(' ', 2)[1]`).
- The remainder (after the key) is processed as follows:
  - If it starts with `"`, read until the closing unescaped `"`, process escapes, and treat everything inside as the value. After the closing quote, optionally read an integer as TTL.
  - Otherwise, the first whitespace‑separated token is the value; a second token, if present, is the TTL.

### LIST response (count‑based)

When a node receives `LIST [prefix]`, it replies with:

```
<count>\n
<key1>\n
<key2>\n
...
<keyN>\n
```

- `<count>` is a non‑negative integer.
- No special terminator line (`END`) is used. The receiving side reads exactly `<count>` lines after the count to obtain all matching keys.

The router aggregates the results from every live node in the same way: it reads a count from each node, collects the corresponding keys, and then sends the client:

```
<total_count>\n
<all_keys_one_per_line>\n
```

The client, after issuing a `LIST` command, first reads a line containing the total count, then reads that many lines for the keys. This completely avoids interference from keys named `END` or starting with `ERROR`.

---

## Module Consolidation & Import Fixes

A single **`protocol.py`** file in the project root will contain all shared functions. All duplicates (e.g., inside `node/`, `client/`, or other subdirectories) must be deleted.

The root `protocol.py` will export:

- `parse_set(line: str) -> tuple(key, value, ttl)`
- `encode_set(key, value, ttl) -> str`
- `encode_list_response(keys: list) -> str`   (returns `count\n` + keys)
- `recv_counted_lines(sock) -> list`          (reads count, then that many lines)

**Mandatory import statements in other modules:**

- `router.py`: `from protocol import encode_list_response, recv_counted_lines`
- `client.py`: `from protocol import recv_counted_lines, encode_list_response`
- `storage_node.py`: `from protocol import parse_set, encode_list_response`

Any existing local parsing logic for SET or LIST will be replaced by calls to these functions.

---

## Detailed File‑by‑File Changes

### 1. `protocol.py` (root)

- Implement `parse_set(line)` as described (quote aware).
- Implement `encode_set(key, value, ttl)` – quotes value only if it contains spaces.
- Implement `recv_counted_lines(sock)`:
  ```python
  def recv_counted_lines(sock):
      count = int(sock.recv_line().strip())
      lines = []
      for _ in range(count):
          lines.append(sock.recv_line().strip())
      return lines
  ```
- Implement `encode_list_response(keys)`:
  ```python
  def encode_list_response(keys):
      return f"{len(keys)}\n" + "\n".join(keys) + "\n"
  ```
- Remove any reference to `END` terminator.

### 2. `router.py`

- Add import:  
  `from protocol import recv_counted_lines, encode_list_response`
- **`_handle_client_set(self, raw_line)`**  
  - Extract the key only using `parts = raw_line.split(' ', 2)` → `parts[1]`.  
  - No further parsing of value/ttl on the router.  
  - Forward the **entire original line** (`raw_line`) to the appropriate storage node. (The node will parse it using `parse_set`.)
- **`_handle_client_list(self, prefix)`**  
  - Send `LIST prefix` to every live node.  
  - For each node, use `recv_counted_lines(node_sock)` to obtain the matching keys.  
  - Aggregate all keys into one flat list.  
  - Reply to the client with `encode_list_response(all_keys)`.
- **`_send_to_node` (internal helper that forwards commands and reads responses)**  
  - For LIST commands, after sending the request, use `recv_counted_lines` to collect the reply.  
  - For SET/GET/DELETE, read a single line response as before.

### 3. `storage_node.py`

- Remove any existing parsing logic for SET (e.g., `args = line.split()`).
- Import `from protocol import parse_set, encode_list_response`
- **Handle `SET`:**  
  ```python
  key, value, ttl = parse_set(full_line)
  self.store[key] = (value, expiry_time)
  self.sock.sendall(b"OK\n")
  ```
- **Handle `LIST [prefix]`:**  
  ```python
  matching = [k for k in self.store if k.startswith(prefix)]
  self.sock.sendall(encode_list_response(matching).encode())
  ```
- No `END` line used. The store is already correctly storing raw values (no splitting).

### 4. `client.py`

- Import `from protocol import recv_counted_lines`
- In the interactive loop or `send_command` method, after sending a `LIST` command:
  - Read the first response line and parse as integer `total_count`.
  - Read exactly `total_count` lines for the keys.
  - Print the keys (one per line).
  - Remove any logic that waits for an `END` line.
- For all other commands (SET, GET, DELETE), continue reading a single‑line response (`OK`, `VALUE ...`, `NOTFOUND`, etc.).

Example snippet inside `send_command`:
```python
if cmd.upper().startswith("LIST"):
    count = int(self.sock.recv_line().strip())
    keys = [self.sock.recv_line().strip() for _ in range(count)]
    print("\n".join(keys))
else:
    response = self.sock.recv_line().strip()
    print(response)
```

### 5. `start.py` (startup script)

The launch script must correctly pass the `--id` argument. The previously planned code had a logic error (wrong directory, missing import). **The updated script must be:**

```python
#!/usr/bin/env python3
import sys
import subprocess
import os
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-nodes", type=int, default=3)
    parser.add_argument("--router-port", type=int, default=9000)
    args = parser.parse_args()

    node_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage_node.py")
    for i in range(args.num_nodes):
        subprocess.Popen([
            sys.executable, node_script,
            "--id", f"node-{i}",
            "--router-host", "localhost",
            "--router-port", str(args.router_port),
            "--vcount", "100"
        ])
    # Optionally run router in foreground
    router_args = [sys.executable, os.path.join(os.path.dirname(__file__), "router.py"),
                   "--port", str(args.router_port)]
    subprocess.run(router_args)

if __name__ == "__main__":
    main()
```

**Key corrections:**
- `__file__` is used to construct the absolute path to `storage_node.py`, ensuring the script is found regardless of the working directory.
- `--id` is explicitly passed as `f"node-{i}"`.
- All other arguments are forwarded correctly.

---

## Concurrency and Consistency

No changes to the concurrency model are required. All protocol modifications are confined to message parsing and do not affect locking or thread safety.

---

## Deployment and Cleanup

- Delete any duplicate `protocol.py` or `storage_node.py` files found in subdirectories. Only the root versions should remain.
- Ensure the root `protocol.py` contains all the functions listed above and is imported by `router.py`, `client.py`, and `storage_node.py`.
- If the project uses `sys.path` modifications to find modules, verify that the root directory is on the path or that imports are adjusted accordingly (standard relative imports or absolute imports from the root).

---

## Verification Checklist

- **Values with spaces**: `SET name "John Doe"` → stored and retrieved correctly.
- **LIST with special keys**: Keys like `END` or `ERROR` do not break the client or router.
- **LIST aggregation**: Router correctly counts and returns all matching keys from multiple nodes.
- **Client display**: CLI client prints LIST output as a count‑based list, no hang.
- **Startup**: `python start.py --num-nodes 3` starts 3 node processes **without** `--id` errors.
- **All regression tests**: GET, DELETE, TTL expiration, node failure and redistribution continue to work.
- **Import verification**: Grep for `from protocol import` confirms every relevant file uses the updated functions.

---

*This revised plan eliminates the disconnection between protocol definition and implementation, fixes the startup bug, and ensures all fixes are effectively applied.*