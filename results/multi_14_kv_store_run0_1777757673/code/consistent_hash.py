"""
Consistent hash ring implementation using MD5 hashes and virtual nodes.

Keys and virtual node names are hashed with MD5 to produce integer hash values.
The ring is a sorted list of (hash_value, node_id) tuples.
"""

import hashlib
import bisect


class ConsistentHashRing:
    """A consistent hash ring that maps string keys to node IDs."""

    def __init__(self, vnodes_per_node: int = 100):
        """
        :param vnodes_per_node: default number of virtual nodes per physical node.
        """
        self.vnodes_per_node = vnodes_per_node
        # Sorted list of (hash_int, node_id) tuples
        self._ring: list[tuple[int, str]] = []
        # Set of registered node ids
        self._nodes: set[str] = set()

    @staticmethod
    def _hash(key: str) -> int:
        """Hash a string key to an integer using MD5."""
        hexdigest = hashlib.md5(key.encode()).hexdigest()
        return int(hexdigest, 16)

    def _vnode_key(self, node_id: str, vindex: int) -> str:
        """Generate a unique virtual node key."""
        return f"{node_id}:vnode:{vindex}"

    def add_node(self, node_id: str, vcount: int = None) -> None:
        """
        Add a physical node with its virtual nodes to the ring.
        :param node_id: unique identifier for the node.
        :param vcount: number of virtual nodes; uses default if None.
        """
        if node_id in self._nodes:
            return  # already added
        if vcount is None:
            vcount = self.vnodes_per_node

        self._nodes.add(node_id)
        for i in range(vcount):
            vkey = self._vnode_key(node_id, i)
            h = self._hash(vkey)
            bisect.insort(self._ring, (h, node_id))

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its virtual nodes from the ring."""
        if node_id not in self._nodes:
            return
        self._nodes.discard(node_id)
        self._ring = [(h, nid) for (h, nid) in self._ring if nid != node_id]
        # Re-sort (they remain sorted but just in case)
        self._ring.sort(key=lambda x: x[0])

    def get_node(self, key: str) -> str | None:
        """
        Return the node_id responsible for the given key.
        Returns None if the ring is empty.
        """
        if not self._ring:
            return None
        h = self._hash(key)
        # Find insertion point for h
        idx = bisect.bisect_left(self._ring, (h, ""))
        if idx == len(self._ring):
            # Wrap around to the first node
            idx = 0
        return self._ring[idx][1]

    @property
    def node_count(self) -> int:
        """Number of physical nodes registered."""
        return len(self._nodes)

    @property
    def nodes(self) -> list[str]:
        """Return list of registered node ids."""
        return list(self._nodes)
