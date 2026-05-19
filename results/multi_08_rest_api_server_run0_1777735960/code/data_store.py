import json
import os
import tempfile
import threading
from typing import Any, Optional


class DataStore:
    """Manages items in-memory with JSON file persistence and thread safety."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.lock = threading.Lock()
        self._items: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load items from the JSON file; if missing, start empty."""
        with self.lock:
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Expect {"items": {...}, "next_id": int}
                    raw = data.get("items", {})
                    # Keys are stored as strings in JSON; convert to int
                    self._items = {int(k): v for k, v in raw.items()}
                    self._next_id = data.get("next_id", 1)
                except (json.JSONDecodeError, ValueError, KeyError):
                    self._items = {}
                    self._next_id = 1
            else:
                self._items = {}
                self._next_id = 1

    def save(self) -> None:
        """Atomically write the current items dict to the JSON file."""
        with self.lock:
            data = {
                "items": {str(k): v for k, v in self._items.items()},
                "next_id": self._next_id,
            }
            fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(self.file_path) or ".",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, self.file_path)  # atomic on POSIX
            except Exception:
                os.unlink(tmp_path)
                raise

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def get_all(self) -> list[dict[str, Any]]:
        """Return all items as a list of dicts (each includes its id)."""
        with self.lock:
            return [{"id": k, **v} for k, v in self._items.items()]

    def get_by_id(self, item_id: int) -> Optional[dict[str, Any]]:
        """Return a single item dict (with id) or None."""
        with self.lock:
            if item_id in self._items:
                return {"id": item_id, **self._items[item_id]}
            return None

    def create(self, item: dict[str, Any]) -> dict[str, Any]:
        """Create a new item, assign an ID, persist, and return it."""
        with self.lock:
            new_id = self._next_id
            self._next_id += 1
            self._items[new_id] = item
            self._save_unlocked()
        return {"id": new_id, **item}

    def update(self, item_id: int, item: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Replace an existing item; return updated item or None if missing."""
        with self.lock:
            if item_id not in self._items:
                return None
            self._items[item_id] = item
            self._save_unlocked()
        return {"id": item_id, **item}

    def delete(self, item_id: int) -> bool:
        """Delete an item; return True if deleted, False if not found."""
        with self.lock:
            if item_id not in self._items:
                return False
            del self._items[item_id]
            self._save_unlocked()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _save_unlocked(self) -> None:
        """Save while already holding self.lock."""
        data = {
            "items": {str(k): v for k, v in self._items.items()},
            "next_id": self._next_id,
        }
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self.file_path) or ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.file_path)
        except Exception:
            os.unlink(tmp_path)
            raise
