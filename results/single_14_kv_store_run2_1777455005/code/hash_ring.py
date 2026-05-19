"""Consistent hash ring for key distribution across storage nodes."""

import hashlib
import bisect


class ConsistentHashRing:
    """A consistent hash ring that maps keys to nodes using virtual nodes."""

    def __init__(self, vnodes_per_node: int = 100):
        self.vnodes_per_node = vnodes_per_node
        self.ring: dict[int, str] = {}  # hash_position -> node_id
        self.sorted_keys: list[int] = []  # sorted list of hash positions

    def add_node(self, node_id: str) -> None:
        """Add a node to the ring with multiple virtual nodes."""
        for i in range(self.vnodes_per_node):
            h = self._hash(f"{node_id}:vnode:{i}")
            self.ring[h] = node_id
        self._rebuild()

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its virtual nodes from the ring."""
        to_remove = [h for h, nid in self.ring.items() if nid == node_id]
        for h in to_remove:
            del self.ring[h]
        self._rebuild()

    def get_node(self, key: str) -> str | None:
        """Find the node responsible for a given key. Returns node_id or None."""
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, h)
        if idx == len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]

    def get_all_nodes(self) -> list[str]:
        """Return list of all unique node IDs in the ring."""
        return list(set(self.ring.values()))

    def _hash(self, key: str) -> int:
        """Hash a key to an integer position on the ring."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def _rebuild(self) -> None:
        """Rebuild the sorted key list after ring changes."""
        self.sorted_keys = sorted(self.ring.keys())
