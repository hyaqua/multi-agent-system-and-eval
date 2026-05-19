"""
Room management: document, OT engine, state, persistence, locks.
"""

import os
import threading
import logging
from collaborative_text_editor.common.protocol import (
    TYPE_OPERATION, TYPE_CURSOR_UPDATE, TYPE_LOCK_GRANT, TYPE_LOCK_RELEASE,
    TYPE_SAVE_ACK, TYPE_USER_JOIN, TYPE_USER_LEAVE,
    OP_INSERT, OP_DELETE,
    make_operation, make_cursor_update, make_lock_grant, make_lock_release,
    make_save_ack, make_user_join, make_user_leave,
)
from collaborative_text_editor.common.ot import apply_operation, inverse_operation, transform

logger = logging.getLogger("server")


class Room:
    """Represents a collaborative editing room with one document."""

    def __init__(self, name, password=None, persist_file=None):
        self.name = name
        self.password = password
        self.persist_file = persist_file

        # Document state
        self.doc = ""
        self.revision = 0
        self.history = []  # list of (revision, username, op) applied operations

        # Load from disk if exists
        if persist_file and os.path.exists(persist_file):
            try:
                with open(persist_file, "r", encoding="utf-8") as f:
                    self.doc = f.read()
                logger.info("Room '%s': loaded document from %s (%d chars)",
                            name, persist_file, len(self.doc))
            except Exception as e:
                logger.error("Room '%s': failed to load %s: %s", name, persist_file, e)

        # Connected clients
        self.clients = {}  # username -> ClientHandler
        self.usernames = []  # ordered list for display

        # Lock management
        self.lock_owner = None  # username or None
        self.lock_queue = []  # FIFO queue of usernames waiting for lock

        # Per-client undo stacks: username -> list of atomic ops (in order applied)
        self.undo_stacks = {}

        # Thread safety
        self.lock = threading.Lock()

        # Cursor positions: username -> (row, col)
        self.cursor_positions = {}

    def add_client(self, handler):
        """Add a client to this room. Called with room lock held."""
        username = handler.username
        self.clients[username] = handler
        if username not in self.usernames:
            self.usernames.append(username)
        if username not in self.undo_stacks:
            self.undo_stacks[username] = []
        logger.info("Room '%s': user '%s' joined (%d users)",
                     self.name, username, len(self.clients))

    def remove_client(self, username):
        """Remove a client. Called with room lock held."""
        if username in self.clients:
            del self.clients[username]
        if username in self.usernames:
            self.usernames.remove(username)
        if username in self.cursor_positions:
            del self.cursor_positions[username]

        # Release lock if this user held it
        if self.lock_owner == username:
            self.lock_owner = None
            self._grant_next_lock()

        logger.info("Room '%s': user '%s' left (%d users)",
                     self.name, username, len(self.clients))

    def broadcast(self, message, exclude=None):
        """Send a message to all connected clients, optionally excluding one."""
        dead = []
        for username, handler in list(self.clients.items()):
            if handler is exclude:
                continue
            try:
                handler.send_message(message)
            except Exception as e:
                logger.warning("Room '%s': failed to send to '%s': %s",
                               self.name, username, e)
                dead.append(username)
        # Clean up dead clients
        for username in dead:
            self.remove_client(username)

    def get_user_list(self):
        """Return list of connected usernames."""
        return list(self.usernames)

    # ---- Lock management ----

    def request_lock(self, username, action):
        """Handle lock request. Returns response message for the requester."""
        if action == "acquire":
            if self.lock_owner == username:
                return make_lock_grant(username)
            if username not in self.lock_queue and self.lock_owner != username:
                self.lock_queue.append(username)
            if self.lock_owner is None and self.lock_queue and self.lock_queue[0] == username:
                self._grant_lock(username)
                return make_lock_grant(username)
            return None  # silently queued
        elif action == "release":
            return self._release_lock(username)
        return None

    def _grant_lock(self, username):
        """Grant lock to username. Called with lock held."""
        self.lock_owner = username
        if username in self.lock_queue:
            self.lock_queue.remove(username)
        logger.info("Room '%s': lock granted to '%s'", self.name, username)
        self.broadcast(make_lock_grant(username))

    def _grant_next_lock(self):
        """Grant lock to next in queue. Called with lock held."""
        if self.lock_queue:
            next_user = self.lock_queue.pop(0)
            self.lock_owner = next_user
            logger.info("Room '%s': lock granted to '%s' (from queue)",
                         self.name, next_user)
            self.broadcast(make_lock_grant(next_user))

    def _release_lock(self, username):
        """Release the lock. Returns message for the requester."""
        if self.lock_owner == username:
            self.lock_owner = None
            logger.info("Room '%s': lock released by '%s'", self.name, username)
            self.broadcast(make_lock_release(username))
            self._grant_next_lock()
            return make_lock_release(username)
        elif username in self.lock_queue:
            self.lock_queue.remove(username)
            return make_lock_release(username)
        return make_lock_release(username)

    # ---- Operation handling ----

    def apply_operation(self, username, msg):
        """
        Apply an operation from a client.
        
        msg contains: id, base_revision, ops (list of {op, pos, char})
        
        Returns the transformed operation message to broadcast, or None on error.
        """
        msg_id = msg.get("id")
        base_revision = msg.get("base_revision", 0)
        ops = msg.get("ops", [])

        if not ops:
            return None

        # Check lock: only lock owner can edit (if there is a lock owner)
        if self.lock_owner is not None and self.lock_owner != username:
            return None

        transformed_ops = []

        for op in ops:
            current_op = dict(op)
            # Transform through all operations from base_revision+1 to current revision
            for rev in range(base_revision + 1, self.revision + 1):
                _, hist_user, hist_op = self.history[rev - 1]  # history is 0-indexed
                # Determine tiebreaker for insert-vs-insert
                tiebreaker = None
                if current_op["op"] == OP_INSERT and hist_op["op"] == OP_INSERT:
                    tiebreaker = username  # the earlier op has already been applied
                current_op = transform(current_op, hist_op, tiebreaker)
                if current_op is None:
                    break  # op became no-op

            if current_op is not None:
                # Apply to document
                old_doc = self.doc
                self.doc = apply_operation(self.doc, current_op)
                transformed_ops.append(current_op)

        if not transformed_ops:
            # All ops became no-ops, still need to ack
            return None

        # Increment revision
        self.revision += 1

        # Store in history
        for op in transformed_ops:
            self.history.append((self.revision, username, op))

        # Add to user's undo stack
        for op in ops:
            self.undo_stacks.setdefault(username, []).append(dict(op))

        # Persist
        self._persist()

        # Build broadcast message
        broadcast_msg = make_operation(msg_id, base_revision, transformed_ops)
        broadcast_msg["username"] = username

        return broadcast_msg

    def handle_undo(self, username):
        """Handle an undo request from a client."""
        if self.lock_owner is not None and self.lock_owner != username:
            return None

        stack = self.undo_stacks.get(username, [])
        if not stack:
            return None

        # Pop the last operation
        last_op = stack.pop()

        # Create inverse
        inv = inverse_operation(last_op)
        if inv is None:
            return None

        # Apply the inverse operation directly (similar to a regular operation)
        import uuid
        msg_id = str(uuid.uuid4())
        fake_msg = {
            "id": msg_id,
            "base_revision": self.revision,
            "ops": [inv],
        }

        result = self.apply_operation(username, fake_msg)
        if result:
            result["is_undo"] = True
        return result

    def handle_cursor_update(self, username, position):
        """Store cursor position and broadcast to others."""
        self.cursor_positions[username] = position
        msg = make_cursor_update(username, self.revision, position)
        # Broadcast to everyone except sender
        for uname, handler in list(self.clients.items()):
            if uname != username:
                try:
                    handler.send_message(msg)
                except Exception as e:
                    logger.warning("Room '%s': failed to send cursor to '%s': %s",
                                   self.name, uname, e)

    def handle_save_request(self, username):
        """Handle explicit save request."""
        self._persist()
        return make_save_ack(username)

    def _persist(self):
        """Write document to disk."""
        if not self.persist_file:
            return
        try:
            with open(self.persist_file, "w", encoding="utf-8") as f:
                f.write(self.doc)
        except Exception as e:
            logger.error("Room '%s': failed to persist: %s", self.name, e)
