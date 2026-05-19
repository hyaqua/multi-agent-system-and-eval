#!/usr/bin/env python3
"""
server.py — Asynchronous TCP server for the collaborative text editor.

Usage:
    python server.py --port 9000 [--config config.json]
"""

import asyncio
import json
import os
import sys
import time
import argparse
import logging
import tempfile
import traceback
from pathlib import Path
from typing import Optional, Dict, List, Set
from collections import defaultdict

import protocol as proto
import ot


# ── Logging ────────────────────────────────────────────────────────────────

def setup_logging(logs_dir: str):
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d")
    log_path = os.path.join(logs_dir, f"server_{timestamp}.log")

    logger = logging.getLogger("server")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Also log to stderr
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


# ── Room ────────────────────────────────────────────────────────────────────

class ClientState:
    __slots__ = ('username', 'client_id', 'reader', 'writer', 'queue',
                 'cursor_offset', 'seq_counter', 'addr')
    def __init__(self, username, client_id, reader, writer, addr):
        self.username = username
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.queue = asyncio.Queue()
        self.cursor_offset = 0
        self.seq_counter = 0
        self.addr = addr


class Room:
    def __init__(self, name: str, password: str, document_file: str,
                 persistence_dir: str, logger: logging.Logger):
        self.name = name
        self.password = password
        self.document_file = document_file
        self.persistence_dir = persistence_dir
        self.logger = logger

        # Document state
        self.document: str = ""
        self.version: int = 0
        self.operations: List[dict] = []  # list of applied ops {op_id, op_type, position, text, length, client_id, version, is_undo}

        # Clients
        self.clients: Dict[str, ClientState] = {}  # client_id -> ClientState

        # Lock
        self.lock_holder: Optional[str] = None  # client_id
        self.lock_queue: asyncio.Queue = asyncio.Queue()

        # Undo stacks: client_id -> list of op_ids
        self.undo_stacks: Dict[str, List[str]] = defaultdict(list)
        self.undone_ops: Set[str] = set()  # op_ids that have been undone

        # Load document
        self._load_document()

    def _load_document(self):
        os.makedirs(self.persistence_dir, exist_ok=True)
        if os.path.exists(self.document_file):
            with open(self.document_file, 'r', encoding='utf-8') as f:
                self.document = f.read()
            self.logger.info(f"Room '{self.name}': loaded document ({len(self.document)} chars)")
        else:
            self.document = ""
            self._persist()
            self.logger.info(f"Room '{self.name}': created empty document")

    def _persist(self):
        """Atomic write of document to disk."""
        os.makedirs(os.path.dirname(self.document_file), exist_ok=True)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(self.document_file),
                suffix='.tmp'
            )
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(self.document)
            os.replace(tmp_path, self.document_file)
        except Exception as e:
            self.logger.error(f"Room '{self.name}': persist failed: {e}")

    def get_user_list(self) -> List[str]:
        return [cs.username for cs in self.clients.values()]

    def get_lock_queue_usernames(self) -> List[str]:
        # Can't peek asyncio.Queue easily; maintain a separate list
        # For simplicity, we track queued clients via a list
        result = []
        # lock_queue holds client_ids
        for item in list(self.lock_queue._queue):
            result.append(item)
        return result

    async def broadcast(self, msg: proto.Message, exclude_client_id: Optional[str] = None):
        """Send message to all connected clients, optionally excluding one."""
        data = proto.encode(msg)
        dead_clients = []
        for cid, cs in self.clients.items():
            if cid == exclude_client_id:
                continue
            try:
                cs.writer.write(data)
                await cs.writer.drain()
            except Exception:
                dead_clients.append(cid)
        for cid in dead_clients:
            await self._remove_client(cid, reason="write error")

    async def send_to(self, client_id: str, msg: proto.Message):
        cs = self.clients.get(client_id)
        if cs:
            try:
                cs.writer.write(proto.encode(msg))
                await cs.writer.drain()
            except Exception:
                await self._remove_client(client_id, reason="write error")

    async def _remove_client(self, client_id: str, reason: str = "disconnect"):
        cs = self.clients.pop(client_id, None)
        if cs is None:
            return
        self.logger.info(
            f"Room '{self.name}': user '{cs.username}' ({client_id}) "
            f"disconnected ({reason})"
        )
        # If held lock, release
        if self.lock_holder == client_id:
            self.lock_holder = None
            await self._process_lock_queue()
            await self.broadcast(proto.LockUpdate(
                holder=None,
                queue=self.get_lock_queue_usernames()
            ))

        # Remove from lock queue
        await self._remove_from_lock_queue(client_id)

        # Broadcast user list update and cursor removal
        await self.broadcast(proto.UserListUpdate(users=self.get_user_list()))
        await self.broadcast(proto.CursorUpdate(
            username=cs.username, line=-1, col=-1, offset=-1
        ))

        try:
            cs.writer.close()
        except Exception:
            pass

    async def _remove_from_lock_queue(self, client_id: str):
        """Remove client from lock queue (rebuild queue)."""
        new_queue = asyncio.Queue()
        while not self.lock_queue.empty():
            item = self.lock_queue.get_nowait()
            if item != client_id:
                await new_queue.put(item)
        self.lock_queue = new_queue

    async def _process_lock_queue(self):
        """Grant lock to next in queue if any."""
        if self.lock_holder is not None:
            return
        if not self.lock_queue.empty():
            next_client = await self.lock_queue.get()
            # Check they're still connected
            if next_client in self.clients:
                self.lock_holder = next_client
                await self.send_to(next_client, proto.LockGrant(holder=next_client))
                await self.broadcast(proto.LockUpdate(
                    holder=self.clients[next_client].username,
                    queue=self.get_lock_queue_usernames()
                ))
                self.logger.info(
                    f"Room '{self.name}': lock granted to "
                    f"'{self.clients[next_client].username}'"
                )
            else:
                # Gone; try next
                await self._process_lock_queue()

    async def handle_connect(self, msg: proto.Connect, reader, writer,
                              client_id: str, addr) -> Optional[proto.Message]:
        """Process a connect message. Returns Ack or Error."""
        if msg.room != self.name:
            return proto.Error(message=f"Wrong room. Expected '{self.name}'")
        if msg.password != self.password:
            self.logger.warning(
                f"Room '{self.name}': failed auth attempt for '{msg.username}'"
            )
            return proto.Error(message="Invalid password")

        # If username already connected, drop old connection
        for cid, cs in list(self.clients.items()):
            if cs.username == msg.username:
                self.logger.info(
                    f"Room '{self.name}': dropping old connection for '{msg.username}'"
                )
                await self._remove_client(cid, reason="replaced by new connection")

        cs = ClientState(
            username=msg.username,
            client_id=client_id,
            reader=reader,
            writer=writer,
            addr=addr,
        )
        self.clients[client_id] = cs

        self.logger.info(
            f"Room '{self.name}': user '{msg.username}' ({client_id}) connected"
        )

        # Send ack
        ack = proto.Ack(
            client_id=client_id,
            document=self.document,
            version=self.version,
            users=self.get_user_list(),
            lock_holder=(
                self.clients[self.lock_holder].username
                if self.lock_holder and self.lock_holder in self.clients
                else None
            ),
        )
        await self.send_to(client_id, ack)

        # Broadcast user list update
        await self.broadcast(proto.UserListUpdate(users=self.get_user_list()),
                             exclude_client_id=client_id)

        return None  # No error

    async def handle_operation(self, msg: proto.Operation, client_id: str) -> Optional[proto.Message]:
        """Process an operation from a client. Returns Error or None."""
        cs = self.clients.get(client_id)
        if cs is None:
            return proto.Error(message="Not connected")

        # Check lock
        if self.lock_holder is not None and self.lock_holder != client_id:
            holder_name = (
                self.clients[self.lock_holder].username
                if self.lock_holder in self.clients
                else "unknown"
            )
            return proto.Error(message=f"Lock held by {holder_name}")

        # Convert to internal OTMessage
        client_op = ot.OTMessage(
            op_type=msg.op_type,
            position=msg.position,
            text=msg.text,
            length=msg.length,
            client_id=client_id,
            seq_no=msg.seq_no,
        )

        # Transform against concurrent operations
        base_version = msg.base_version
        transformed_op = client_op

        if base_version < self.version:
            for i in range(base_version, self.version):
                logged = self.operations[i]
                concurrent = ot.OTMessage(
                    op_type=logged['op_type'],
                    position=logged['position'],
                    text=logged.get('text', ''),
                    length=logged.get('length', 0),
                    client_id=logged['client_id'],
                    seq_no=logged.get('seq_no', 0),
                )
                transformed_op = ot.transform(transformed_op, concurrent)
        elif base_version > self.version:
            return proto.Error(message="Client ahead of server version")

        # Validate the transformed operation
        if transformed_op.op_type == "insert":
            if transformed_op.position < 0 or transformed_op.position > len(self.document):
                return proto.Error(message=f"Invalid insert position: {transformed_op.position}")
        elif transformed_op.op_type == "delete":
            if (transformed_op.position < 0 or
                transformed_op.length <= 0 or
                transformed_op.position + transformed_op.length > len(self.document)):
                return proto.Error(message=f"Invalid delete: pos={transformed_op.position}, len={transformed_op.length}, doc_len={len(self.document)}")

        # Apply to document
        old_doc = self.document
        self.document = ot.apply_operation(self.document, transformed_op)

        # Record the operation
        op_id = f"{client_id}:{self.version}"
        op_record = {
            'op_id': op_id,
            'op_type': transformed_op.op_type,
            'position': transformed_op.position,
            'text': transformed_op.text,
            'length': transformed_op.length,
            'client_id': client_id,
            'version': self.version,
            'is_undo': False,
            'seq_no': msg.seq_no,
        }
        self.operations.append(op_record)
        old_version = self.version
        self.version += 1

        # Update undo stack for this client
        self.undo_stacks[client_id].append(op_id)

        # Persist
        self._persist()

        self.logger.info(
            f"Room '{self.name}': op by '{cs.username}': "
            f"{transformed_op.op_type}@{transformed_op.position} "
            f"len={transformed_op.length} v={old_version}→{self.version}"
        )

        # Broadcast to other clients
        broadcast_op = proto.Operation(
            op_type=transformed_op.op_type,
            position=transformed_op.position,
            text=transformed_op.text,
            length=transformed_op.length,
            base_version=self.version,
            client_id=client_id,
            seq_no=msg.seq_no,
            op_id=op_id,
        )
        await self.broadcast(broadcast_op, exclude_client_id=client_id)

        # Ack to sender
        ack = proto.OperationAck(
            seq_no=msg.seq_no,
            op_id=op_id,
            op_type=transformed_op.op_type,
            position=transformed_op.position,
            text=transformed_op.text,
            length=transformed_op.length,
            new_version=self.version,
            client_id=client_id,
        )
        await self.send_to(client_id, ack)

        return None

    async def handle_undo(self, msg: proto.UndoRequest, client_id: str) -> Optional[proto.Message]:
        """Handle an undo request."""
        cs = self.clients.get(client_id)
        if cs is None:
            return proto.Error(message="Not connected")

        # Check lock
        if self.lock_holder is not None and self.lock_holder != client_id:
            holder_name = (
                self.clients[self.lock_holder].username
                if self.lock_holder in self.clients
                else "unknown"
            )
            return proto.Error(message=f"Lock held by {holder_name}")

        # Find the most recent non-undone op from this client
        stack = self.undo_stacks.get(client_id, [])
        op_to_undo_id = None
        op_to_undo_index = -1
        for i in range(len(stack) - 1, -1, -1):
            if stack[i] not in self.undone_ops:
                op_to_undo_id = stack[i]
                op_to_undo_index = i
                break

        if op_to_undo_id is None:
            return proto.Error(message="Nothing to undo")

        # Find the operation record
        op_record = None
        op_record_version = -1
        for rec in self.operations:
            if rec['op_id'] == op_to_undo_id:
                op_record = rec
                op_record_version = rec['version']
                break

        if op_record is None:
            return proto.Error(message="Operation not found for undo")

        # Compute the document state BEFORE the original operation
        # We need to reconstruct doc at that point
        doc_before = self._reconstruct_document_at(op_record_version)

        # Compute inverse
        orig_op = ot.OTMessage(
            op_type=op_record['op_type'],
            position=op_record['position'],
            text=op_record.get('text', ''),
            length=op_record.get('length', 0),
            client_id=client_id,
            seq_no=0,
        )
        inverse_op = ot.inverse(orig_op, doc_before)

        # Now transform the inverse against all operations after op_record_version
        transformed_inverse = inverse_op
        for i in range(op_record_version + 1, len(self.operations)):
            later = self.operations[i]
            concurrent = ot.OTMessage(
                op_type=later['op_type'],
                position=later['position'],
                text=later.get('text', ''),
                length=later.get('length', 0),
                client_id=later['client_id'],
                seq_no=later.get('seq_no', 0),
            )
            transformed_inverse = ot.transform(transformed_inverse, concurrent)

        # Validate
        if transformed_inverse.op_type == "insert":
            if transformed_inverse.position < 0 or transformed_inverse.position > len(self.document):
                return proto.Error(message=f"Undo resulted in invalid position")
        elif transformed_inverse.op_type == "delete":
            if (transformed_inverse.position < 0 or
                transformed_inverse.length <= 0 or
                transformed_inverse.position + transformed_inverse.length > len(self.document)):
                return proto.Error(message=f"Undo resulted in invalid delete")

        # Apply
        self.document = ot.apply_operation(self.document, transformed_inverse)

        # Record
        op_id = f"{client_id}:{self.version}"
        op_record_new = {
            'op_id': op_id,
            'op_type': transformed_inverse.op_type,
            'position': transformed_inverse.position,
            'text': transformed_inverse.text,
            'length': transformed_inverse.length,
            'client_id': client_id,
            'version': self.version,
            'is_undo': True,
            'seq_no': -1,
        }
        self.operations.append(op_record_new)
        self.version += 1

        # Mark original as undone
        self.undone_ops.add(op_to_undo_id)

        # Persist
        self._persist()

        self.logger.info(
            f"Room '{self.name}': undo by '{cs.username}' — "
            f"reversed {op_to_undo_id}"
        )

        # Broadcast
        broadcast_op = proto.Operation(
            op_type=transformed_inverse.op_type,
            position=transformed_inverse.position,
            text=transformed_inverse.text,
            length=transformed_inverse.length,
            base_version=self.version,
            client_id=client_id,
            seq_no=-1,
            op_id=op_id,
        )
        await self.broadcast(broadcast_op, exclude_client_id=client_id)

        # Ack (as operation_ack)
        ack = proto.OperationAck(
            seq_no=-1,
            op_id=op_id,
            op_type=transformed_inverse.op_type,
            position=transformed_inverse.position,
            text=transformed_inverse.text,
            length=transformed_inverse.length,
            new_version=self.version,
            client_id=client_id,
        )
        await self.send_to(client_id, ack)

        return None

    def _reconstruct_document_at(self, target_version: int) -> str:
        """Reconstruct document state at a given version by replaying operations."""
        doc = ""
        for i in range(target_version):
            rec = self.operations[i]
            op_msg = ot.OTMessage(
                op_type=rec['op_type'],
                position=rec['position'],
                text=rec.get('text', ''),
                length=rec.get('length', 0),
                client_id=rec['client_id'],
                seq_no=0,
            )
            doc = ot.apply_operation(doc, op_msg)
        return doc

    async def handle_cursor_update(self, msg: proto.CursorUpdate, client_id: str):
        cs = self.clients.get(client_id)
        if cs is None:
            return
        cs.cursor_offset = msg.offset
        # Broadcast to others
        await self.broadcast(
            proto.CursorUpdate(
                username=cs.username,
                line=msg.line,
                col=msg.col,
                offset=msg.offset,
            ),
            exclude_client_id=client_id,
        )

    async def handle_lock_request(self, msg: proto.LockRequest, client_id: str):
        cs = self.clients.get(client_id)
        if cs is None:
            return
        if self.lock_holder == client_id:
            # Already holds lock; release it
            await self.handle_lock_release(
                proto.LockRelease(client_id=client_id), client_id
            )
            return
        if self.lock_holder is None:
            # Grant immediately
            self.lock_holder = client_id
            await self.send_to(client_id, proto.LockGrant(holder=cs.username))
            await self.broadcast(proto.LockUpdate(
                holder=cs.username,
                queue=self.get_lock_queue_usernames()
            ))
            self.logger.info(
                f"Room '{self.name}': lock granted to '{cs.username}'"
            )
        else:
            # Queue
            await self.lock_queue.put(client_id)
            await self.broadcast(proto.LockUpdate(
                holder=self.clients[self.lock_holder].username
                if self.lock_holder in self.clients else None,
                queue=self.get_lock_queue_usernames()
            ))
            self.logger.info(
                f"Room '{self.name}': lock queued for '{cs.username}'"
            )

    async def handle_lock_release(self, msg: proto.LockRelease, client_id: str):
        cs = self.clients.get(client_id)
        if cs is None:
            return
        if self.lock_holder != client_id:
            return  # Not the holder
        self.lock_holder = None
        self.logger.info(f"Room '{self.name}': lock released by '{cs.username}'")
        await self._process_lock_queue()
        await self.broadcast(proto.LockUpdate(
            holder=(
                self.clients[self.lock_holder].username
                if self.lock_holder and self.lock_holder in self.clients
                else None
            ),
            queue=self.get_lock_queue_usernames()
        ))

    async def handle_save_request(self, msg: proto.SaveRequest, client_id: str):
        cs = self.clients.get(client_id)
        if cs is None:
            return
        self._persist()
        await self.send_to(client_id, proto.SaveAck())
        self.logger.info(f"Room '{self.name}': save requested by '{cs.username}'")


# ── Server ──────────────────────────────────────────────────────────────────

class Server:
    def __init__(self, host: str, port: int, config_path: str):
        self.host = host
        self.port = port
        self.config_path = config_path
        self.config = {}
        self.logger: Optional[logging.Logger] = None
        self.rooms: Dict[str, Room] = {}
        self._client_id_counter = 0

    def _next_client_id(self) -> str:
        self._client_id_counter += 1
        return f"c{self._client_id_counter}"

    def load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        logs_dir = self.config.get("logs_dir", "logs")
        self.logger = setup_logging(logs_dir)

        persistence_dir = self.config.get("persistence_dir", "documents")
        for room_name, room_cfg in self.config.get("rooms", {}).items():
            self.rooms[room_name] = Room(
                name=room_name,
                password=room_cfg["password"],
                document_file=room_cfg["document_file"],
                persistence_dir=persistence_dir,
                logger=self.logger,
            )
            self.logger.info(f"Room '{room_name}' initialized")

    async def handle_client(self, reader: asyncio.StreamReader,
                            writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        self.logger.info(f"New connection from {addr}")

        client_id = self._next_client_id()
        room: Optional[Room] = None
        client_state: Optional[ClientState] = None

        try:
            # First message must be connect
            line = await asyncio.wait_for(reader.readline(), timeout=30)
            if not line:
                self.logger.info(f"Client {addr} disconnected before connect")
                return

            try:
                msg = proto.decode(line.decode('utf-8').strip())
            except Exception as e:
                self.logger.error(f"Invalid message from {addr}: {e}")
                writer.write(proto.encode(proto.Error(message=f"Invalid message: {e}")))
                await writer.drain()
                return

            if not isinstance(msg, proto.Connect):
                writer.write(proto.encode(
                    proto.Error(message="First message must be 'connect'")
                ))
                await writer.drain()
                return

            room_name = msg.room
            if room_name not in self.rooms:
                writer.write(proto.encode(
                    proto.Error(message=f"Unknown room: {room_name}")
                ))
                await writer.drain()
                return

            room = self.rooms[room_name]
            error = await room.handle_connect(msg, reader, writer, client_id, addr)
            if error is not None:
                writer.write(proto.encode(error))
                await writer.drain()
                return

            client_state = room.clients.get(client_id)
            if client_state is None:
                return

            # Main message loop
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=300)
                if not line:
                    break

                try:
                    msg = proto.decode(line.decode('utf-8').strip())
                except Exception as e:
                    self.logger.error(f"Parse error from {client_state.username}: {e}")
                    await room.send_to(client_id,
                        proto.Error(message=f"Parse error: {e}"))
                    continue

                error = None

                if isinstance(msg, proto.Operation):
                    error = await room.handle_operation(msg, client_id)
                elif isinstance(msg, proto.CursorUpdate):
                    await room.handle_cursor_update(msg, client_id)
                elif isinstance(msg, proto.LockRequest):
                    await room.handle_lock_request(msg, client_id)
                elif isinstance(msg, proto.LockRelease):
                    await room.handle_lock_release(msg, client_id)
                elif isinstance(msg, proto.SaveRequest):
                    await room.handle_save_request(msg, client_id)
                elif isinstance(msg, proto.UndoRequest):
                    error = await room.handle_undo(msg, client_id)
                elif isinstance(msg, proto.Connect):
                    error = proto.Error(message="Already connected")
                elif isinstance(msg, proto.Disconnect):
                    break
                else:
                    error = proto.Error(message=f"Unknown message type: {msg.type}")

                if error is not None:
                    await room.send_to(client_id, error)

        except asyncio.TimeoutError:
            self.logger.info(f"Client {addr} timed out")
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            self.logger.info(f"Client {addr} connection error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error for {addr}: {e}")
            traceback.print_exc()
        finally:
            if room and client_id:
                await room._remove_client(client_id, reason="disconnect")

    async def start(self):
        self.load_config()
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        self.logger.info(f"Server listening on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Collaborative Text Editor Server")
    parser.add_argument("--port", type=int, default=9000, help="TCP port")
    parser.add_argument("--config", type=str, default="config.json",
                        help="Config file path")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Bind address")
    args = parser.parse_args()

    server = Server(host=args.host, port=args.port, config_path=args.config)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("Server shutting down.")


if __name__ == "__main__":
    main()
