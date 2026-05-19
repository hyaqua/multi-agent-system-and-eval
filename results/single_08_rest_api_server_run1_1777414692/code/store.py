"""
JSON file-based data store for items. Thread-safe.
"""

import json
import os
import threading
from typing import Optional


class ItemStore:
    """Thread-safe store that persists items to a JSON file."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._next_id = 1
        self._load()

    # ------------------------------------------------------------------
    # Internal persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load items from the JSON file, or initialise empty."""
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # data is expected to be {"items": [...], "next_id": int}
                items_list = data.get("items", [])
                self._items = {}
                max_id = 0
                for item in items_list:
                    item_id = str(item.get("id", ""))
                    if item_id:
                        self._items[item_id] = item
                        try:
                            num = int(item_id)
                            if num > max_id:
                                max_id = num
                        except ValueError:
                            pass
                self._next_id = max_id + 1
            except (json.JSONDecodeError, IOError):
                self._items = {}
                self._next_id = 1
        else:
            self._items = {}
            self._next_id = 1

    def _save(self) -> None:
        """Persist items to the JSON file."""
        data = {
            "items": list(self._items.values()),
            "next_id": self._next_id,
        }
        with open(self._filepath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    # ------------------------------------------------------------------
    # Public CRUD API
    # ------------------------------------------------------------------

    def all(self, filters: Optional[dict] = None) -> list[dict]:
        """Return all items, optionally filtered by field=value pairs."""
        with self._lock:
            items = list(self._items.values())
            if filters:
                filtered = []
                for item in items:
                    match = True
                    for key, value in filters.items():
                        if str(item.get(key, "")) != str(value):
                            match = False
                            break
                    if match:
                        filtered.append(item)
                return filtered
            return items

    def get(self, item_id: str) -> Optional[dict]:
        """Return a single item by ID, or None."""
        with self._lock:
            return self._items.get(item_id)

    def create(self, data: dict) -> dict:
        """Create a new item; returns the created item with assigned id."""
        with self._lock:
            item_id = str(self._next_id)
            self._next_id += 1
            item = {"id": item_id, **data}
            self._items[item_id] = item
            self._save()
            return dict(item)

    def update(self, item_id: str, data: dict) -> Optional[dict]:
        """Update an existing item. Returns updated item or None."""
        with self._lock:
            existing = self._items.get(item_id)
            if existing is None:
                return None
            # Merge: preserve the id, update other fields
            updated = {"id": item_id, **data}
            self._items[item_id] = updated
            self._save()
            return dict(updated)

    def delete(self, item_id: str) -> bool:
        """Delete an item. Returns True if deleted, False if not found."""
        with self._lock:
            if item_id not in self._items:
                return False
            del self._items[item_id]
            self._save()
            return True
