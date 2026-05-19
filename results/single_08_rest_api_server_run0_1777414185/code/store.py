"""
Thread-safe JSON file data store for items.
"""
import json
import os
import threading
import uuid


class DataStore:
    """Persistent, thread-safe storage for items backed by a JSON file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lock = threading.Lock()
        self.items: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load items from the JSON file (if it exists)."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as fh:
                try:
                    data = json.load(fh)
                except json.JSONDecodeError:
                    data = []
            # Index by 'id' for O(1) lookups
            self.items = {item["id"]: item for item in data if "id" in item}
        else:
            self.items = {}
            self._save()

    def _save(self) -> None:
        """Persist current items to the JSON file."""
        with open(self.filepath, "w", encoding="utf-8") as fh:
            json.dump(list(self.items.values()), fh, indent=2)

    # ------------------------------------------------------------------
    # Public CRUD operations (all acquire the lock)
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        """Return a shallow copy of every stored item."""
        with self.lock:
            return list(self.items.values())

    def get(self, item_id: str) -> dict | None:
        """Return a single item by id, or *None*."""
        with self.lock:
            return self.items.get(item_id)

    def create(self, data: dict) -> dict:
        """
        Create a new item.  If *data* already contains an 'id' it is
        preserved; otherwise a UUID is generated.
        """
        with self.lock:
            item_id = data.get("id") or str(uuid.uuid4())
            item = {"id": item_id}
            item.update(data)
            self.items[item_id] = item
            self._save()
            return dict(item)

    def update(self, item_id: str, data: dict) -> dict | None:
        """
        Update fields of an existing item.  The 'id' field is never
        overwritten.  Returns the updated item or *None*.
        """
        with self.lock:
            if item_id not in self.items:
                return None
            item = self.items[item_id]
            item.update(data)
            item["id"] = item_id  # guard against accidental overwrite
            self._save()
            return dict(item)

    def delete(self, item_id: str) -> bool:
        """Remove an item.  Returns *True* on success, *False* if missing."""
        with self.lock:
            if item_id not in self.items:
                return False
            del self.items[item_id]
            self._save()
            return True
