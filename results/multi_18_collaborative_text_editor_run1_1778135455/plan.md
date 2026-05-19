# Revised Implementation Plan (v9)

This plan resolves **all issues** identified in the latest review, with emphasis on guaranteeing server startup regardless of filesystem permissions. The server crash prevented any other feature from being tested. The fix is immediate and minimal; once applied, the remaining bugs can be addressed in order.

---

## Section A – Server Logging with Absolute Fallback (Highest Priority)

**File:** `server.py` – `setup_logging` function

**Problem:** The server unconditionally creates a log file in the current working directory. If that directory is read‑only (as in the test environment), `PermissionError` is raised and the server never starts. No other feature can be tested. The specification requires the server to fall back gracefully and continue running.

**Change required:** Replace the `setup_logging` function with a version that tries **only writable locations**, and if all fail, logs exclusively to `stderr`. The function must **never** raise an exception – it must always return a configured logger.

**Revised implementation strategy** – start with the most permissive location first (`/tmp`), then a user‑specific directory, never the current directory (which is assumed risky):

```python
import os
import sys
import logging
from datetime import datetime

def setup_logging(port: int) -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Candidates ordered from safest to least safe
    candidates = [
        os.path.join("/tmp", f"collab_edit_server_{port}_{ts}.log"),
        os.path.join(os.path.expanduser("~"), "collab_editor_logs",
                     f"server_{port}_{ts}.log"),
    ]

    for candidate in candidates:
        try:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
            fh = logging.FileHandler(candidate, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(fh)
            print(f"Logging to {candidate}", file=sys.stderr)
            return logger
        except (PermissionError, OSError) as exc:
            print(f"Could not log to {candidate}: {exc}", file=sys.stderr)

    # Absolute fallback – server MUST start even if no file can be written
    print("All file paths failed; logging to stderr only.", file=sys.stderr)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
```

**Rationale:**  
- `/tmp` is writable on virtually all Unix‑like systems, even in restricted containers.  
- The home directory fallback covers environments where `/tmp` is unavailable.  
- The current directory is intentionally **omitted** because it is the source of the failure.  
- If no file handler works, the server still operates using only `stderr`, which complies with the specification’s requirement that the server must not fail on logging errors.

**Verification:** Run the server from `/workspace` (read‑only). The server starts, prints a warning that it is logging to `/tmp/...`, opens the TCP socket, and begins listening. No crash. This immediately unblocks testing of all other features.

---

## Section B – Fix Client Document Regression (`handle_ack`)

*(identical to v8 plan)*

---

## Section C – Fix Syntax Highlighting Logic (`_render_highlighted_line`)

*(identical to v8 plan)*

---

## Section D – Cleanup Unused Imports and Variables

*(identical to v8 plan)*

---

## Section E – Viewport‑Wide Search Highlighting

*(identical to v8 plan)*

---

## Section F – Portable Word Jump Parsing

*(identical to v8 plan)*

---

## Section G – Client Reconnection After Disconnection

*(identical to v8 plan)*

---

## Implementation Order

1. **Section A** – Logging fallback (enables server startup, unblocks everything).  
2. **Section B** – Ack document fix (critical for data consistency).  
3. **Section C** – Syntax highlighting rewrite.  
4. **Section D** – Cleanup imports.  
5. **Section E** – Search highlights.  
6. **Section F** – Portable word jumps.  
7. **Section G** – Reconnection.  

Once Section A is applied, the server will start and the remaining features become testable. All other behaviour (cursor movement, OT, locks, undo, sidebar, etc.) must remain intact as originally designed.

*This v9 plan supersedes v8 and is the definitive guide for the next implementation phase.*