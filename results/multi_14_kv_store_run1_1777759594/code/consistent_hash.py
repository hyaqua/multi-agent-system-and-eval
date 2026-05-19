"""
consistent_hash.py — Consistent hashing ring with virtual nodes.

Maps string keys to node IDs using Python's built-in hash().
"""
import bisect
import hashlib


class ConsistentHashRing:
    """Consistent hash ring using virtual nodes."""

    def __init__(self, virtual_nodes: int = 128):
        """
        Args:
            virtual_nodes: Number of virtual nodes per physical node.
        """
        self.virtual_nodes = virtual_nodes
        # Sorted list of virtual-node hashes
        self._ring: list[int] = []
        # hash -> node_id mapping
        self._hash_to_node: dict[int, str] = {}
        # node_id -> set of virtual hashes
        self._node_hashes: dict[str, set[int]] = {}

    def _hash(self, key: str) -> int:
        """Hash a string key to an integer in a large space."""
        h = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(h, 16)

    def add_node(self, node_id: str) -> None:
        """Add a physical node with its virtual nodes."""
        if node_id in self._node_hashes:
            return  # already present
        self._node_hashes[node_id] = set()
        for i in range(self.virtual_nodes):
            vkey = f"{node_id}:vn:{i}"
            vhash = self._hash(vkey)
            self._node_hashes[node_id].add(vhash)
            self._hash_to_node[vhash] = node_id
            bisect.insort(self._ring, vhash)

    def remove_node(self, node_id: str) -> None:
        """Remove a physical node and all its virtual nodes."""
        hashes = self._node_hashes.pop(node_id, set())
        for h in hashes:
            self._hash_to_node.pop(h, None)
            idx = bisect.bisect_left(self._ring, h)
            if idx < len(self._ring) and self._ring[idx] == h:
                del self._ring[idx]

    def get_node(self, key: str) -> str | None:
        """
        Return the node_id responsible for a given key.
        Returns None if the ring is empty.
        """
        if not self._ring:
            return None
        khash = self._hash(key)
        idx = bisect.bisect_right(self._ring, khash)
        if idx == len(self._ring):
            idx = 0  # wrap around
        vhash = self._ring[idx]
        return self._hash_to_node[vhash]

    def get_nodes(self) -> list[str]:
        """Return list of all registered node IDs."""
        return list(self._node_hashes.keys())

    def empty(self) -> bool:
        """Return True if no nodes registered."""
        return len(self._ring) == 0
