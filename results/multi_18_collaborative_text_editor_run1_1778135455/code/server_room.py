"""
Room management for the collaborative editor server.

Each room holds:
- A document (flat string)
- An operation log (for undo)
- Per-client undo stacks
- A lock queue
- Connected client info
- Version counter
"""

import os
import threading
import logging
from typing import Dict, List

import ot
import protocol

logger = logging.getLogger("server.room")


class Room:
    """A document room with versioned operations and lock management."""

    def __init__(self, name: str, storage_dir: str = "./rooms"):
        self.name = name
        self.storage_dir = storage_dir
        self.lock = threading.Lock()

        # Document state
        self.document: str = ""
        self.version: int = 0

        # Operation log: list of (version, op, user)
        self.op_log: list[tuple[int, ot.Op, str]] = []

        # Per-client undo stacks: user -> list of log indices
        self.undo_stacks: dict[str, list[int]] = {}

        # Connected clients: user -> dict with color, handler ref
        self.clients: dict[str, dict] = {}

        # Lock state
        self.lock_holder: str | None = None
        self.lock_queue: list[str] = []

        # Color assignment
        self._next_color: int = 0
        self._available_colors: list[int] = list(range(1, 9))  # colors 1-8

        # Load from disk if exists
        self._load_from_disk()

    # ── Document persistence ────────────────────────────────────────────────

    def _file_path(self) -> str:
        os.makedirs(self.storage_dir, exist_ok=True)
        safe_name = "".join(c for c in self.name if c.isalnum() or c in "._-")
        return os.path.join(self.storage_dir, f"{safe_name}.txt")

    def _load_from_disk(self):
        path = self._file_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.document = f.read()
                logger.info("Room '%s': loaded document (%d chars) from %s",
                            self.name, len(self.document), path)
            except IOError as e:
                logger.error("Room '%s': failed to load document: %s", self.name, e)
                self.document = ""

    def save_to_disk(self):
        """Write the current document to disk."""
        path = self._file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.document)
            logger.debug("Room '%s': saved document (%d chars) to %s",
                         self.name, len(self.document), path)
        except IOError as e:
            logger.error("Room '%s': failed to save document: %s", self.name, e)

    # ── Client management ───────────────────────────────────────────────────

    def add_client(self, user: str) -> int:
        """Register a client. Returns assigned color index."""
        with self.lock:
            if user in self.clients:
                # Reconnecting – keep their old color
                color = self.clients[user]["color"]
            else:
                color = self._assign_color()
            self.clients[user] = {"color": color, "cursor_pos": 0}
            if user not in self.undo_stacks:
                self.undo_stacks[user] = []
            logger.info("Room '%s': client '%s' joined (color %d)",
                        self.name, user, color)
            return color

    def remove_client(self, user: str):
        """Unregister a client."""
        with self.lock:
            if user in self.clients:
                color = self.clients[user]["color"]
                self._release_color(color)
                del self.clients[user]
                logger.info("Room '%s': client '%s' left (color %d)",
                            self.name, user, color)
            # If lock holder leaves, release lock
            if self.lock_holder == user:
                self.lock_holder = None
                self._grant_next_lock()

    def get_clients_list(self) -> list[dict]:
        """Return list of connected client info."""
        with self.lock:
            return [
                {"user": u, "color": c["color"], "cursor_pos": c["cursor_pos"]}
                for u, c in self.clients.items()
            ]

    def _assign_color(self) -> int:
        if self._available_colors:
            return self._available_colors.pop(0)
        # All colors used, cycle
        used = {c["color"] for c in self.clients.values()}
        for c in range(1, 9):
            if c not in used:
                return c
        self._next_color = (self._next_color % 8) + 1
        return self._next_color

    def _release_color(self, color: int):
        if color not in self._available_colors:
            self._available_colors.append(color)
            self._available_colors.sort()

    # ── Operations ──────────────────────────────────────────────────────────

    def process_operation(self, op_dict: dict, user: str) -> tuple[dict | None, dict | None]:
        """Process an incoming operation from a client.

        Args:
            op_dict: The operation message from the client.
            user: The username sending the operation.

        Returns:
            (ack_message, broadcast_message) – ack goes to sender,
            broadcast goes to all (including sender for cursor sync).
            Returns (error, None) on failure.
        """
        with self.lock:
            # Check lock
            if self.lock_holder is not None and self.lock_holder != user:
                return protocol.make_error("Document is locked by " + self.lock_holder), None

            base_version = op_dict.get("base_version", 0)
            op_type = op_dict.get("op", "")
            pos = op_dict.get("pos", 0)
            text = op_dict.get("text", "")
            op_id = op_dict.get("op_id", 0)

            if op_type not in ("insert", "delete"):
                return protocol.make_error("Invalid operation type"), None

            # Validate position
            if op_type == "insert":
                if pos < 0 or pos > len(self.document):
                    return protocol.make_error(f"Invalid insert position {pos}"), None
            else:  # delete
                if pos < 0 or pos + len(text) > len(self.document):
                    return protocol.make_error(f"Invalid delete range {pos}:{pos+len(text)}"), None
                # Enrich delete with actual text from document
                actual_text = self.document[pos:pos + len(text)]
                if text and text != actual_text:
                    # Client's text doesn't match – use actual
                    text = actual_text

            client_op = ot.Op(op_type, pos, text)

            # Transform against operations since base_version
            transformed_op = client_op.copy()
            for v in range(base_version + 1, self.version + 1):
                log_op = self.op_log[v - 1][1]  # op_log is 0-indexed, version is 1-indexed
                transformed_op = ot.transform(transformed_op, log_op, "left")

            # Apply to document
            try:
                self.document = ot.apply_op(self.document, transformed_op)
            except (IndexError, ValueError) as e:
                logger.error("Failed to apply op: %s (doc len=%d)", e, len(self.document))
                return protocol.make_error(f"Failed to apply operation: {e}"), None

            # Increment version
            self.version += 1

            # Store in log
            self.op_log.append((self.version, transformed_op.copy(), user))

            # Push to user's undo stack
            self.undo_stacks.setdefault(user, []).append(len(self.op_log) - 1)

            # Save to disk
            self.save_to_disk()

            # Build ack for sender
            ack = {
                "type": protocol.TYPE_OPERATION,
                "op": transformed_op.op,
                "pos": transformed_op.pos,
                "text": transformed_op.text,
                "version": self.version,
                "op_id": op_id,
                "ack": True,
                "user": user,
            }

            # Build broadcast for all
            broadcast = {
                "type": protocol.TYPE_OPERATION,
                "op": transformed_op.op,
                "pos": transformed_op.pos,
                "text": transformed_op.text,
                "version": self.version,
                "user": user,
            }

            logger.debug("Room '%s' v%d: %s by %s: %s",
                         self.name, self.version, op_type, user, transformed_op)

            return ack, broadcast

    # ── Undo ────────────────────────────────────────────────────────────────

    def process_undo(self, user: str) -> dict | None:
        """Process an undo request. Returns broadcast message or None."""
        with self.lock:
            if self.lock_holder is not None and self.lock_holder != user:
                return None

            stack = self.undo_stacks.get(user, [])
            if not stack:
                return None

            log_index = stack.pop()
            _, original_op, op_user = self.op_log[log_index]

            # Compute inverse of original op
            inv_op = ot.invert(original_op)

            # Transform inverse against all subsequent ops
            transformed_inv = inv_op.copy()
            for i in range(log_index + 1, len(self.op_log)):
                subsequent_op = self.op_log[i][1]
                transformed_inv = ot.transform(transformed_inv, subsequent_op, "left")

            # Apply inverse to document
            self.document = ot.apply_op(self.document, transformed_inv)

            # Increment version
            self.version += 1

            # Store in log (but NOT on undo stack)
            self.op_log.append((self.version, transformed_inv.copy(), user))

            # Save
            self.save_to_disk()

            broadcast = {
                "type": protocol.TYPE_OPERATION,
                "op": transformed_inv.op,
                "pos": transformed_inv.pos,
                "text": transformed_inv.text,
                "version": self.version,
                "user": user,
            }

            logger.debug("Room '%s' v%d: undo by %s: %s",
                         self.name, self.version, user, transformed_inv)

            return broadcast

    # ── Lock management ────────────────────────────────────────────────────

    def request_lock(self, user: str) -> tuple[dict | None, dict | None]:
        """Handle a lock request. Returns (grant_msg, status_broadcast)."""
        with self.lock:
            if self.lock_holder == user:
                return None, None  # Already holds lock
            if self.lock_holder is None:
                self.lock_holder = user
                grant = protocol.make_lock_grant(user)
                status = protocol.make_lock_status(user, list(self.lock_queue))
                logger.info("Room '%s': lock granted to '%s'", self.name, user)
                return grant, status
            else:
                if user not in self.lock_queue:
                    self.lock_queue.append(user)
                status = protocol.make_lock_status(self.lock_holder, list(self.lock_queue))
                logger.info("Room '%s': lock queued for '%s' (holder: '%s')",
                            self.name, user, self.lock_holder)
                return None, status

    def release_lock(self, user: str) -> dict | None:
        """Handle a lock release. Returns status broadcast or None."""
        with self.lock:
            if self.lock_holder != user:
                # Remove from queue if present
                if user in self.lock_queue:
                    self.lock_queue.remove(user)
                    return protocol.make_lock_status(self.lock_holder, list(self.lock_queue))
                return None

            self.lock_holder = None
            logger.info("Room '%s': lock released by '%s'", self.name, user)

            # Grant to next in queue
            return self._grant_next_lock()

    def _grant_next_lock(self) -> dict | None:
        if self.lock_queue:
            next_user = self.lock_queue.pop(0)
            self.lock_holder = next_user
            logger.info("Room '%s': lock granted to '%s' (from queue)", self.name, next_user)
            # Note: grant message sent separately via ClientHandler
            return protocol.make_lock_status(next_user, list(self.lock_queue))
        else:
            return protocol.make_lock_status(None, [])

    def get_lock_holder(self) -> str | None:
        with self.lock:
            return self.lock_holder

    # ── Cursor ─────────────────────────────────────────────────────────────

    def update_cursor(self, user: str, pos: int):
        with self.lock:
            if user in self.clients:
                self.clients[user]["cursor_pos"] = max(0, pos)
