# Revised Implementation Plan: Collaborative Real‑Time Text Editor (v9)

This plan addresses all feedback from the review, fixing bootstrap issues first, then implementing missing features with robust and conflict‑free designs. Every point from the review is covered, and the implementation order ensures no feature is blocked by unfinished prerequisites.

---

## 1. Critical Bootstrap and State Propagation Fixes

### 1.1 Make `server/server.py` Launchable from Any Context
*Identical to previous plan.*  
Add the following at the very top of `server/server.py` **before any other import**:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

All subsequent imports remain fully qualified (e.g. `from collaborative_text_editor.server.room import Room`).  
**Verification**: start the server with both `python server/server.py` and `python -m collaborative_text_editor.server.server` – no `ModuleNotFoundError`.

### 1.2 Propagate Initial User List and Lock Owner to TUI & Fix Sidebar
The client’s `connect()` receives an `ack` containing `users` (full list of connected users in the room) and `lock_owner`. Currently this data is not forwarded to the TUI and the sidebar only shows users who have sent cursor updates.

**Changes in `client/client.py`**:
1. Inside `connect()`, after receiving the ack:
   ```python
   self.initial_users = ack['users']
   self.initial_lock_owner = ack.get('lock_owner')
   ```
2. Pass this data to the TUI **before the event loop starts**. For example, in the function that creates `TUI`:
   ```python
   tui.set_connected_users(client.initial_users)    # full list
   tui.set_lock_owner(client.initial_lock_owner)
   ```

**Changes in `client/tui.py`**:
- Remove any code that builds the sidebar from `editor.remote_cursors`. Instead, store the full user list as an instance variable `connected_users`.
- `set_connected_users(users)` – updates this list, rebuilds sidebar, and refreshes.
- On receiving subsequent `cursor_update` messages from the server, still update the remote cursor positions but **do not** alter the sidebar user list unless a `join` or `leave` message arrives.
- Implement server‑to‑client notifications for user join/leave (if not already present) by broadcasting an `update_users` message whenever the room’s user list changes. Ensure the sidebar always reflects the current connected users.

### 1.3 Flake8 Cleanup
Remove all unused imports, variables, and trailing whitespace. Specifically:
- Delete the unused `old_doc` assignment in `server/room.py`.
- Remove every unused import (e.g., modules imported but never referenced).
- Fix indentation and whitespace inconsistencies.
Run `flake8` from the project root and eliminate **all** warnings before proceeding.

---

## 2. Feature Implementations (in Required Order)

### 2.1 Operational Transformation Tiebreaker (Username‑Based)
*The review confirms tiebreaker is missing.*  
Inside `common/ot.py`, modify `_transform_insert_insert` to accept a `tiebreaker` tuple `(username_a, username_b)`.

**Logic**:
- If insert positions `p1 == p2`, compare `username_a` and `username_b` lexicographically.
- The insert from the lexicographically **smaller** username keeps its original position; the other’s position is shifted by `len(content)`.
- Update `transform(op1, op2, tiebreaker)` to forward the tiebreaker.
- In `server/room.py`, when two operations are being transformed concurrently, supply the originating client usernames.

This guarantees deterministic document state regardless of operation order.

### 2.2 Server‑Side Undo – Correct Inverse Using Transformed Operations
*Review feedback: storing original (untransformed) ops leads to wrong inverse after concurrent edits.*  
**Revised approach**:

- After the server applies and transforms an operation, store the **transformed operation** (exactly what was broadcast) in a per‑user stack, along with its revision number.
- When an `undo` request arrives for a user:
  - Pop the last transformed operation from that user’s stack.
  - Compute its **inverse**: if it was an insert at position `p` of length `l`, create a delete operation at `p` for `l` characters; if it was a delete, create an insert with the deleted content at `p`.
  - Set the base revision to the current document revision and submit it through the normal `apply_operation` pipeline as a new operation by that user.
  - Broadcast the resulting (possibly further transformed) inverse operation to all clients.
- This ensures the inverse exactly reverses the effect that the original transformed operation had, even after concurrent edits.

**Protocol**: define a new `undo` message (client→server) containing the client’s current revision.

### 2.3 Word‑Jumping (Ctrl+Left / Ctrl+Right) Robustness
- Read multiple bytes to capture escape sequences such as `\033[1;5D` (Ctrl+Left) and `\033[1;5C` (Ctrl+Right).
- Also react to `curses.KEY_SLEFT` / `KEY_SRIGHT` if the terminal supports them.
- As a fallback, handle `Alt+B` (`\033b`) and `Alt+F` (`\033f`) which many terminals map to backward/forward word.
- Movement logic: define a function `is_word_char(ch)` that returns true for alphanumerics and underscore. Skip to the next/previous boundary where `is_word_char` changes.

### 2.4 Search Previous Match – Reliable Key Detection
- In raw mode, `Shift+Enter` often sends `\033[Z` or `\033[13;2u` (kitty extended). Handle both.
- Use a small state machine: if `\033` is received, collect the subsequent bytes and try to parse as an escape sequence.
- If the sequence matches a known pattern for Shift+Enter, move to the previous match.
- Additionally, provide **explicit alternative keys**: `Ctrl+P` for previous match and `Ctrl+N` for next match, so that users have a reliable fallback.

### 2.5 Operation Logging
The server log must record every confirmed operation (after transformation). Each log line includes:
- Timestamp (ISO 8601)
- Room name
- Username
- Operation type (`insert`/`delete`), position, content (first 50 chars if longer)
- Resulting document revision number

Example:
```
2025-03-21T10:15:22 [room: python] user alice INSERT pos=42 content="import os\n" rev=105
```

Implement in `server/room.py` by writing to the same timestamped log file used for connections/disconnections.

### 2.6 Find‑and‑Replace Correctness (Per‑Replacement Confirmation)
*The bug: sequential replace‑all logic uses local applies without batching, causing index mismatches.*  
Even though the requirement is per‑replacement confirmation, the underlying logic must remain consistent.

**Fix**:
- When the user confirms a replacement, immediately apply it locally and send the corresponding operation to the server.
- After the replacement, **re‑search** from the newly replaced position for the next occurrence. Because the document has changed, the previous list of match positions is invalid. Use `find_next_match(text, last_replaced_position)`.
- Discard any pre‑computed “match list” after each replacement; always search forward from the current position.
- Ensure the cursor is moved to the next match (or wraps around).

This avoids any index drift and keeps the workflow simple.

### 2.7 Concurrency and Regression Testing
Run a comprehensive integration test with at least **10 clients** connected to **two rooms**. The test must include:
- Rapid concurrent inserts, deletes, and cursor movements.
- Multiple lock/unlock cycles.
- Undo operations from different clients after concurrent edits (validate document consistency).
- Find‑and‑replace across multiple clients.
- Word‑jumping and viewport scrolling correct.

Validate that all clients see identical document content and no deadlocks or data corruption occur.

---

## 3. Implementation Order

1. **Server startup fix** (Section 1.1) – verify import works from any launch method.
2. **Client ACK propagation & sidebar fix** (1.2) – ensure full user list and lock owner are shown on connection.
3. **Flake8 cleanup** (1.3) – zero warnings.
4. **OT tiebreaker** (2.1) – integrate usernames.
5. **Undo with transformed ops** (2.2).
6. **Robust word‑jumping** (2.3).
7. **Reliable search previous match** (2.4).
8. **Operation logging** (2.5).
9. **Find‑and‑replace correctness** (2.6).
10. **Concurrency & regression testing** (2.7).

Each step must be tested in isolation before moving to the next. The server and client fixes (steps 1‑3) are absolute prerequisites for all further work.