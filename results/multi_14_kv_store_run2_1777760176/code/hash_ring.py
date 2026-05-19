"""
hash_ring.py – Consistent hashing ring implementation.

Uses MD5 for key hashing and virtual nodes to distribute keys evenly.
Supports add_node, remove_node, and get_node for routing a key to the owning node.
"""

import hashlib
import bisect
import threading


class HashRing:
    """Consistent hashing ring with virtual nodes."""

    def __init__(self, virtual_nodes_per_node: int = 128):
        self.virtual_nodes_per_node = virtual_nodes_per_node
        self.lock = threading.Lock()

        # Sorted list of ring positions (hash integers)
        self._ring: list[int] = []
        # Map: position -> node_id
        self._pos_to_node: dict[int, str] = {}
        # Map: node_id -> list of positions (virtual nodes)
        self._node_positions: dict[str, list[int]] = {}
        # Map: node_id -> (host, port)
        self._node_info: dict[str, tuple[str, int]] = {}

    def _hash(self, key: str) -> int:
        """Hash a key to an integer in [0, 2**128-1]."""
        digest = hashlib.md5(key.encode()).digest()
        return int.from_bytes(digest, byteorder="big")

    def _make_vnode_key(self, node_id: str, vnode_index: int) -> str:
        """Create a virtual-node key string for hashing."""
        return f"vnode:{node_id}:{vnode_index}"

    def add_node(self, node_id: str, host: str, port: int):
        """Add a physical node with its virtual nodes to the ring."""
        with self.lock:
            if node_id in self._node_info:
                # Already exists; remove old virtual nodes first
                self._remove_node_locked(node_id)

            self._node_info[node_id] = (host, port)
            positions = []

            for i in range(self.virtual_nodes_per_node):
                vkey = self._make_vnode_key(node_id, i)
                pos = self._hash(vkey)
                positions.append(pos)
                self._pos_to_node[pos] = node_id
                bisect.insort(self._ring, pos)

            self._node_positions[node_id] = positions

    def remove_node(self, node_id: str):
        """Remove a physical node and all its virtual nodes from the ring."""
        with self.lock:
            self._remove_node_locked(node_id)

    def _remove_node_locked(self, node_id: str):
        """Remove node without acquiring the lock (must be called with lock held)."""
        if node_id not in self._node_positions:
            return

        for pos in self._node_positions[node_id]:
            if pos in self._pos_to_node:
                del self._pos_to_node[pos]
            idx = bisect.bisect_left(self._ring, pos)
            if idx < len(self._ring) and self._ring[idx] == pos:
                self._ring.pop(idx)

        del self._node_positions[node_id]

        if node_id in self._node_info:
            del self._node_info[node_id]

    def get_node(self, key: str) -> tuple[str, str, int] | None:
        """
        Given a key, return the (node_id, host, port) of the owning node,
        or None if the ring is empty.
        """
        with self.lock:
            if not self._ring:
                return None

            key_hash = self._hash(key)
            # Find first virtual node position >= key_hash
            idx = bisect.bisect_left(self._ring, key_hash)

            if idx == len(self._ring):
                idx = 0  # wrap around

            pos = self._ring[idx]
            node_id = self._pos_to_node[pos]
            host, port = self._node_info[node_id]
            return node_id, host, port

    def get_all_nodes(self) -> list[tuple[str, str, int]]:
        """Return list of (node_id, host, port) for all registered nodes."""
        with self.lock:
            return [(nid, info[0], info[1]) for nid, info in self._node_info.items()]

    @property
    def node_count(self) -> int:
        with self.lock:
            return len(self._node_info)
