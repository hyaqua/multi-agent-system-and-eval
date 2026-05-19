"""
Shared protocol constants and utilities for the distributed key-value store.
"""
import hashlib
import bisect
import threading

# Default ports
DEFAULT_CLIENT_PORT = 5555
DEFAULT_NODE_PORT = 5556
DEFAULT_NODE_START_PORT = 6000

# Protocol delimiters
LINE_TERM = '\n'

# Router <-> Node commands
CMD_PUT = 'PUT'
CMD_GET = 'GET'
CMD_DELETE = 'DELETE'
CMD_KEYS = 'KEYS'
CMD_PING = 'PING'
CMD_REGISTER = 'REGISTER'

# Node <-> Router responses
RESP_OK = 'OK'
RESP_VALUE = 'VALUE'
RESP_NOT_FOUND = 'NOT_FOUND'
RESP_DELETED = 'DELETED'
RESP_KEYS = 'KEYS'
RESP_PONG = 'PONG'
RESP_ERROR = 'ERROR'

# Client <-> Router commands
CMD_CLI_SET = 'SET'
CMD_CLI_GET = 'GET'
CMD_CLI_DELETE = 'DELETE'
CMD_CLI_LIST = 'LIST'
CMD_CLI_QUIT = 'QUIT'
CMD_CLI_EXIT = 'EXIT'


class ConsistentHash:
    """Consistent hashing ring with virtual nodes."""

    def __init__(self, virtual_nodes=100):
        self.virtual_nodes = virtual_nodes
        self.ring = []  # sorted list of (hash_int, node_id)
        self.nodes = set()  # set of node_ids
        self.lock = threading.RLock()

    def _hash(self, key: str) -> int:
        """Hash a key to an integer in [0, 2^128)."""
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)

    def add_node(self, node_id: str) -> None:
        """Add a node with virtual nodes to the ring."""
        with self.lock:
            if node_id in self.nodes:
                return
            self.nodes.add(node_id)
            for i in range(self.virtual_nodes):
                h = self._hash(f"{node_id}:vn:{i}")
                self.ring.append((h, node_id))
            self.ring.sort(key=lambda x: x[0])

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its virtual nodes from the ring."""
        with self.lock:
            self.nodes.discard(node_id)
            self.ring = [(h, nid) for h, nid in self.ring if nid != node_id]

    def get_node(self, key: str) -> str | None:
        """Find the node responsible for a given key."""
        with self.lock:
            if not self.ring:
                return None
            h = self._hash(key)
            # Binary search for the first hash >= key hash
            idx = bisect.bisect_left(self.ring, (h, ""))
            if idx >= len(self.ring):
                idx = 0
            return self.ring[idx][1]

    def all_nodes(self) -> list:
        """Return a copy of all node IDs."""
        with self.lock:
            return list(self.nodes)

    def node_count(self) -> int:
        """Return the number of nodes."""
        with self.lock:
            return len(self.nodes)
