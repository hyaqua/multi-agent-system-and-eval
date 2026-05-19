## Revised Implementation Plan (v12) – Mandatory Fixes for Review Feedback

This plan specifies **all** required changes to resolve the missing features and bugs identified in the review. Every directive below is mandatory and must be implemented **exactly** as written. The existing implementation must be altered so that no contradictory logic remains. All previously working features (listed in the specification) must continue to operate correctly.

The revisions directly address the following review findings:

- **Missing features**: Search using Ctrl+P, prompt text, multi‑line Python syntax highlighting, remote cursor label length (username[:3]), client OT pipeline, word‑jumping regex, raw‑byte escape parser.
- **Bugs**: Multi‑line string tokenisation, inverse‑based `handle_ack`, truncated remote cursor label, incorrect word movement with `isalnum()`, flake8 warnings, absent integration tests.

---

### 1. Escape‑Sequence Parser (Raw‑Byte State Machine) – Mandatory Replacement

The entire key‑handling layer **must** be replaced with a pure raw‑byte state machine. No `curses.KEY_*` constants or magic numbers may remain. The word‑jumping logic **must** abandon the `isalnum()` approach and use the required regex.

- Implement `parse_key_event()` reading from `stdscr.getch()`.
- Supported sequences (exhaustive):
  - `\x1b[A` → `('up',)`
  - `\x1b[B` → `('down',)`
  - `\x1b[C` → `('right',)`
  - `\x1b[D` → `('left',)`
  - `\x1b[H` or `\x1b[1~` → `('home',)`
  - `\x1b[F` or `\x1b[4~` → `('end',)`
  - `\x1b[5~` → `('page_up',)`
  - `\x1b[6~` → `('page_down',)`
  - `\x1b[3~` → `('delete',)`
  - `\x1b[1;5D` or `\x1b[5D` → `('ctrl_left',)`
  - `\x1b[1;5C` or `\x1b[5C` → `('ctrl_right',)`
  - All other escape sequences → silently discard.
- ASCII 0x20–0x7E → `('char', chr(byte))`
- `\x7f` or `\x08` → `('backspace',)`
- `\n` or `\r` → `('enter',)`
- `\t` → `('tab',)`
- `\x10` (Ctrl+P) → `('ctrl_p',)` – used **only** in search bar for previous match.
- Control characters that map to hotkeys (e.g., Ctrl+S, Ctrl+Z, etc.) are handled directly in the high‑level loop, **not** by the parser.
- **Word‑jumping** (Ctrl+Left/Right) **must** be implemented using `re.finditer(r'\b\w+\b', line)` without any splitting on whitespace or punctuation. All existing `isalnum()`‑based code must be removed.

---

### 2. Search – Ctrl+P for Previous Match

When the search bar is open (triggered by `Ctrl+F`):

- `Enter` → next match.
- `Ctrl+P` (raw byte `0x10`) → **previous match, wrapping at boundaries**. No Shift+Enter may navigate matches.
- `Esc` → close search bar.
- The prompt text **must** read exactly:  
  `Search: _ (Enter=next, Ctrl+P=prev, Esc=cancel)`
- The search string must not change when `Ctrl+P` is pressed.

---

### 3. Multi‑line Python Syntax Highlighting – Stateful `tokenize_document`

Replace all per‑line tokenisation (the flawed `tokenize_line`) with a single, document‑wide function:

```python
Token = namedtuple('Token', ['text', 'color'])

def tokenize_document(lines: List[str]) -> List[List[Token]]:
    # State: None, 'single', 'double', 'triple_single', 'triple_double'
    ...
```

- Triple‑quoted strings (`'''` and `"""`) are recognised when they open (not part of a single‑line string) and set the state appropriately.
- While the state is `triple_single` or `triple_double`, every line is coloured entirely with the string colour; no keyword/number/comment parsing.
- When the closing triple quote is encountered, the state resets and the remainder of that line (if any) is tokenised normally.
- `_draw_document()` must call `tokenize_document()` once per frame for the entire document and render using the returned per‑line token lists. This fully fixes the multi‑line string bug.

---

### 4. Remote Cursor Label – Exactly `username[:3]`

- For each remote user whose cursor is visible, draw a label on the row immediately above the cursor’s line (or same row if at top edge).
- The label text must be `username[:3]` (first three characters). The current single‑character truncation (`username[:1]`) must be removed.
- Use the user’s assigned colour pair.
- Examples: `"Alice"` → `"Ali"`, `"Bo"` → `"Bo"`, `"Z"` → `"Z"`.

---

### 5. Client OT Pipeline – Exact Replacement (Critical)

The current inverse‑based `handle_ack` and the optimistic update logic **must** be completely removed and replaced by the algorithms below. This corrects document desynchronisation bugs.

#### `apply_remote_op(remote_op)`

```python
def apply_remote_op(remote_op):
    # Transform remote op against all pending local ops
    op = remote_op
    for pending_op, _, _ in self.pending_ops:
        op = transform(op, pending_op)

    # Apply transformed op to base document
    self.base_document = apply_op(self.base_document, op)

    # Transform every pending local op against the ORIGINAL remote_op
    new_pending = []
    for p_op, base_version, local_seq in self.pending_ops:
        new_pending.append((transform(p_op, remote_op), base_version, local_seq))
    self.pending_ops = new_pending

    # Update cursor and version
    self.cursor = transform_cursor(self.cursor, op)
    self.local_version = remote_op.version
```

#### `handle_ack(ack_message)`

```python
def handle_ack(ack_message):
    # Find the acknowledged pending op by local_seq_no
    idx = next((i for i, (_, _, seq) in enumerate(self.pending_ops)
                if seq == ack_message.local_seq_no), None)
    if idx is None:
        return

    # Remove it and transform remaining pending ops against server's transformed_op
    new_pending = []
    for i, (op, bv, seq) in enumerate(self.pending_ops):
        if i == idx:
            continue
        new_pending.append((transform(op, ack_message.transformed_op), bv, seq))
    self.pending_ops = new_pending

    # Apply server's transformed operation to base document
    self.base_document = apply_op(self.base_document, ack_message.transformed_op)

    # Update version and cursor
    self.local_version = ack_message.new_version
    self.cursor = transform_cursor(self.cursor, ack_message.transformed_op)
```

- `apply_op` must return a new document (immutable update).
- `transform` is the existing OT function (unchanged).
- `transform_cursor` adjusts a cursor position according to an operation.
- All contrary logic (inverse‑based handling, reapplying local ops differently) must be purged.

---

### 6. Code Quality – Zero `flake8` Warnings

The entire project must pass `flake8 . --max-line-length=119` with **no warnings**. Fix all:

- Unused imports
- Unused local variables (e.g., `doc` in cursor methods)
- Missing/extra blank lines
- Trailing whitespace
- Long lines (>119)
- Any other violations.

---

### 7. Mandatory Integration Tests

Add the following eight integration tests. Each must be self‑contained and pass without disrupting existing tests:

1. **Escape‑parser**: feed raw bytes for all defined keys and verify correct tokens.
2. **Search Ctrl+P**: activate Ctrl+F, send `\x10`, assert highlight moves to previous match.
3. **Multi‑line syntax**: load a `.py` with a triple‑quoted string spanning lines; check interior lines are string‑coloured.
4. **Remote cursor label**: connect a second user with name >3 chars; assert label shows `username[:3]`.
5. **OT – remote transforms pending ops**: two clients edit concurrently; final documents must be identical and match server.
6. **OT – ack ordering**: acknowledgements arrive out of order; pending ops are correctly transformed, document matches server.
7. **Lock queue usernames**: multiple clients; lock‑holder’s full username appears in notifications (sidebar/status bar) as sent by server.
8. **flake8 compliance**: run `flake8 . --max-line-length=119` and assert zero output.

---

### 8. Preservation of Working Features

The fixes above must not break any of the following correctly functioning features:

- Server `--port` / client `--user` / `--room` arguments
- Password authentication
- Document persistence after each confirmed operation
- Server‑side OT logic
- Client curses TUI: line numbers, status bar, sidebar, viewport scrolling
- Editing operations (insert, backspace, delete, Enter)
- Optimistic local updates
- Real‑time remote edits and cursor display
- Ctrl+S save, Ctrl+H find‑and‑replace, Ctrl+L lock, Ctrl+Z undo
- All JSON message types and TCP protocol
- Full‑state reconnection and server logging
- 10‑client concurrency

---

### 9. Execution Order

1. **Replace** client OT pipeline with the exact `apply_remote_op` and `handle_ack` above.
2. **Implement** the raw‑byte escape‑sequence parser and remove all old key handling, including the `isalnum()` word‑jump logic.
3. **Implement** `tokenize_document` and replace per‑line tokenisation in drawing.
4. **Add** Ctrl+P handling in search bar and correct the prompt text.
5. **Fix** remote cursor label to `username[:3]`.
6. **Ensure** lock notifications use the full username from the server message.
7. **Eliminate** all flake8 warnings.
8. **Write** the eight integration tests.
9. **Run** all tests (old and new) to guarantee no regressions.
10. **Verify** end‑to‑end with 10 concurrent clients, reconnection, and file persistence.

**Every step must be verified before continuing. The final deliverable must pass all tests and satisfy every mandatory requirement.**