"""
storage.py - In-memory item collection with JSON file persistence and thread-safe writes.
"""

import json
import threading
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ItemStorage:
    """Manages a list of item dicts, persisted to a JSON file."""

    def __init__(self, file_path: str = "items.json"):
        self._file_path = Path(file_path)
        self._lock = threading.RLock()
        self._items: list[dict] = []
        self._next_id: int = 1
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self):
        """Load items from the JSON file if it exists."""
        if self._file_path.exists():
            try:
                with open(self._file_path, "r") as f:
                    data = json.load(f)
                self._items = data.get("items", [])
                self._next_id = data.get("next_id", 1)
                logger.info("Loaded %d items from %s", len(self._items), self._file_path)
            except (json.JSONDecodeError, IOError) as exc:
                logger.error("Failed to load items: %s", exc)
                self._items = []
                self._next_id = 1
        else:
            self._items = []
            self._next_id = 1
            logger.info("No existing data file; starting empty.")

    def _save(self):
        """Persist items to the JSON file under the lock."""
        with self._lock:
            try:
                data = {"items": self._items, "next_id": self._next_id}
                with open(self._file_path, "w") as f:
                    json.dump(data, f, indent=2)
            except IOError as exc:
                logger.error("Failed to save items: %s", exc)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        """Return a shallow copy of all items."""
        with self._lock:
            return list(self._items)

    def get_by_id(self, item_id: int) -> dict | None:
        """Return a single item by its id, or None."""
        with self._lock:
            for item in self._items:
                if item.get("id") == item_id:
                    return dict(item)  # return a copy
            return None

    def add(self, item: dict) -> dict:
        """Add a new item.  Assigns a new id. Returns the created item."""
        with self._lock:
            new_item = dict(item)
            new_item["id"] = self._next_id
            self._next_id += 1
            self._items.append(new_item)
            self._save()
            return dict(new_item)

    def update(self, item_id: int, data: dict) -> dict | None:
        """Update an existing item.  *data* may be partial. Returns updated item or None."""
        with self._lock:
            for i, item in enumerate(self._items):
                if item.get("id") == item_id:
                    merged = dict(item)
                    # Merge in new data but preserve the id.
                    merged.update(data)
                    merged["id"] = item_id
                    self._items[i] = merged
                    self._save()
                    return dict(merged)
            return None

    def delete(self, item_id: int) -> bool:
        """Delete an item by id.  Returns True if deleted, False otherwise."""
        with self._lock:
            for i, item in enumerate(self._items):
                if item.get("id") == item_id:
                    del self._items[i]
                    self._save()
                    return True
            return False

    def filter_by_field(self, params: dict) -> list[dict]:
        """
        Return items where *all* key-value pairs in *params* match exactly.
        All values are compared as strings (query-string values are always strings).
        """
        with self._lock:
            if not params:
                return list(self._items)

            result = []
            for item in self._items:
                match = True
                for key, wanted in params.items():
                    actual = item.get(key)
                    if actual is None:
                        match = False
                        break
                    # Compare as strings because query values are strings.
                    if str(actual) != wanted:
                        match = False
                        break
                if match:
                    result.append(dict(item))
            return result
