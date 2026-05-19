"""
Client-side document model with optimistic updates and OT.

Maintains:
- synced_doc: The document as last acknowledged by the server.
- pending_ops: Local operations not yet acknowledged.
- local_doc: synced_doc + pending_ops applied = what the user sees.
- synced_version: The server version of synced_doc.
"""

import logging
from typing import List

import ot
import protocol

logger = logging.getLogger("client.edit")


class Document:
    """Client-side document with optimistic update support."""

    def __init__(self, initial_text: str = "", version: int = 0):
        self.synced_doc: str = initial_text
        self.synced_version: int = version
        self.pending_ops: list[dict] = []  # list of {op, op_id, ...}
        self._next_op_id: int = 0
        # Track server-acknowledged ops by op_id
        self._acked_ids: set = set()

    @property
    def local_doc(self) -> str:
        """The full document with pending ops applied (what the user sees)."""
        doc = self.synced_doc
        for p in self.pending_ops:
            op = ot.Op(p["op"], p["pos"], p["text"])
            doc = ot.apply_op(doc, op)
        return doc

    def get_local_doc(self) -> str:
        return self.local_doc

    def insert(self, pos: int, text: str) -> dict:
        """Optimistically insert text. Returns the operation message to send."""
        op_id = self._next_op_id
        self._next_op_id += 1

        op_msg = protocol.make_operation(
            op="insert",
            pos=pos,
            text=text,
            base_version=self.synced_version,
            op_id=op_id,
        )

        self.pending_ops.append({
            "op": "insert",
            "pos": pos,
            "text": text,
            "op_id": op_id,
        })

        return op_msg

    def delete(self, pos: int, text: str) -> dict:
        """Optimistically delete text. Returns the operation message."""
        op_id = self._next_op_id
        self._next_op_id += 1

        op_msg = protocol.make_operation(
            op="delete",
            pos=pos,
            text=text,
            base_version=self.synced_version,
            op_id=op_id,
        )

        self.pending_ops.append({
            "op": "delete",
            "pos": pos,
            "text": text,
            "op_id": op_id,
        })

        return op_msg

    def apply_remote_op(self, remote_op_msg: dict):
        """Apply a remote operation from the server.

        Transforms it against pending ops and applies to both
        synced_doc and pending_ops.
        """
        remote_op = ot.Op(
            remote_op_msg["op"],
            remote_op_msg["pos"],
            remote_op_msg["text"],
        )
        remote_version = remote_op_msg.get("version", self.synced_version + 1)
        remote_user = remote_op_msg.get("user", "")

        # Transform remote op against each pending op (right side)
        transformed = remote_op.copy()
        for p in self.pending_ops:
            pending_op = ot.Op(p["op"], p["pos"], p["text"])
            transformed = ot.transform(transformed, pending_op, "right")

        # Apply transformed remote op to synced_doc
        self.synced_doc = ot.apply_op(self.synced_doc, transformed)
        self.synced_version = max(self.synced_version, remote_version)

        # Transform each pending op against the remote op (left side)
        new_pending = []
        for p in self.pending_ops:
            pending_op = ot.Op(p["op"], p["pos"], p["text"])
            new_op = ot.transform(pending_op, remote_op, "left")
            p["op"] = new_op.op
            p["pos"] = new_op.pos
            p["text"] = new_op.text
            new_pending.append(p)
        self.pending_ops = new_pending

        logger.debug("Remote op applied: %s by %s (v%d)",
                     transformed, remote_user, self.synced_version)

    def handle_ack(self, ack_msg: dict):
        """Handle a server acknowledgement for a pending operation."""
        op_id = ack_msg.get("op_id", -1)
        ack_version = ack_msg.get("version", self.synced_version)

        # Find and remove the acknowledged op from pending
        found = False
        new_pending = []
        for p in self.pending_ops:
            if p["op_id"] == op_id and not found:
                # This is the acknowledged op
                found = True
                # Apply it to synced_doc permanently
                op = ot.Op(p["op"], p["pos"], p["text"])
                # The op is already in synced_doc via pending application,
                # but we need to update synced_version.
                # Actually the synced_doc should now match the server state.
                continue
            new_pending.append(p)
        self.pending_ops = new_pending

        if found:
            self.synced_version = max(self.synced_version, ack_version)
            logger.debug("Ack received for op_id=%d (v%d)", op_id, ack_version)
        else:
            # Could be an ack from the server for a broadcast op
            # (server sends operation with ack=True to originator)
            # If we didn't generate this op_id, it's a broadcast echo
            # Just update version
            self.synced_version = max(self.synced_version, ack_version)

    def full_resync(self, document: str, version: int):
        """Full resync with server state (used on reconnect)."""
        self.synced_doc = document
        self.synced_version = version
        self.pending_ops.clear()
        logger.info("Full resync: doc=%d chars, v=%d", len(document), version)

    def cursor_pos_to_line_col(self, pos: int) -> tuple[int, int]:
        """Convert flat cursor position to (line, col)."""
        doc = self.local_doc
        if pos <= 0:
            return 0, 0
        lines = doc[:pos].split("\n")
        return len(lines) - 1, len(lines[-1])

    def line_col_to_pos(self, line: int, col: int) -> int:
        """Convert (line, col) to flat cursor position."""
        doc = self.local_doc
        lines = doc.split("\n")
        if line < 0:
            line = 0
        if line >= len(lines):
            return len(doc)
        pos = 0
        for i in range(line):
            pos += len(lines[i]) + 1  # +1 for newline
        pos += min(col, len(lines[line]))
        return pos
