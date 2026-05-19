## Revised Implementation Plan: Simple Git-like Version Control System (`vcs`)

This plan corrects the import issues identified during review. **All cross‑module imports are absolute sibling imports**, allowing `vcs.py` to run directly as the entry point without any package context. Unused imports have been removed and import clarity has been improved.

### 1. File Structure & Purposes

```
vcs/                          # all source modules (siblings)
├── vcs.py                    # CLI entry point, argument parsing, dispatch
├── repository.py             # Core repository: init, object/blob storage, refs, index, commit logic
├── commands.py               # Implementation of each subcommand
└── utils.py                  # Hashing, binary detection, diff generation, error handling
```

**Invocation:** users place `vcs/` anywhere (e.g., `~/tools/vcs/`) and run from the project root:

```bash
python ~/tools/vcs/vcs.py <command>
```

When `vcs.py` is executed directly, its containing directory is added to `sys.path`. Thus `import repository`, `from utils import …`, etc. work without any package setup.

### 2. Import Strategy (Mandatory)

**Only absolute sibling imports are allowed.** No module uses `from .sibling import …`. Every cross‑module reference uses the plain module name.

Detailed import requirements for each file:

- **`vcs.py`**
  ```python
  import repository
  from commands import handle_init, handle_status, ...   # or import commands
  ```
  It imports `repository.is_initialized()` and `repository.get_repo_root()` for pre‑command checks, then dispatches to `commands`.

- **`commands.py`**
  ```python
  import repository
  from utils import compute_blob_hash, is_binary, generate_diff, ...
  ```
  Never imports from `utils` with relative syntax. It calls repository functions for all filesystem access.

- **`repository.py`**
  ```python
  from utils import compute_blob_hash, is_binary
  ```
  It never imports from `commands`.

- **`utils.py`** – no internal imports (pure standard library).

No module uses `from . import ...`; no module uses `from __future__` or any package‑relative syntax. This strict rule guarantees that `vcs.py` is runnable directly.

**Additionally**, to keep imports clean:
- Remove unused imports (e.g. `os` if not needed in `vcs.py` after the check, `shutil` if not used in `repository.py`, and any unused imports in `commands.py`). Only import what is actually used.

### 3. Architecture & Data Model (unchanged)

Identical to original: `.vcs/` directory with `HEAD`, `index.json`, `objects/`, `refs/heads/`. Content‑addressable blobs and JSON commits.

- **Blob:** `SHA256("blob " + length + "\0" + content)`
- **Commit:** JSON map with `tree`, `parent`, `author`, `timestamp`, `message`.  
  Hashed similarly.
- **Index:** `index.json` mapping file path → blob hash.
- **Refs:** branch files (e.g., `refs/heads/master`) containing the latest commit hash.
- **HEAD:** either `ref: refs/heads/master` or a commit hash (detached).

### 4. Module Interactions (updated)

- **`vcs.py`** (entry point):
  1. If the command is `init`, proceed directly.
  2. For all other commands, call `repository.is_initialized()` (checks current directory for `.vcs`).
  3. Parse arguments, then call the appropriate function from `commands` (e.g., `commands.handle_status(args)`), passing the current working directory as repo root.
- **`commands.py`** uses `repository` functions for all `.vcs` manipulation and `utils` for hashing/diff/binary detection.
- **`repository.py`** handles all filesystem I/O under `.vcs`; uses `utils` only for hashing.
- **`utils.py`** is pure logic.

All imports use absolute sibling style as described.

### 5. Implementation Order (unchanged)

1. `utils.py` – core utilities.
2. `repository.py` – object storage, refs, index, init.
3. `vcs.py` – CLI scaffold with subcommand dispatch; integrate `init` first.
4. `commands.py` – add one command at a time, after the required repository methods exist.

### 6. Feature Implementation Details (unchanged)

Every subcommand (`init`, `status`, `add`, `commit`, `log`, `diff`, `checkout`, `branch`, `switch`) follows the original design. Edge cases (binary file detection, deduplication, detached HEAD, branching) remain the same.

### 7. Adjustments to Avoid Import Errors (mandatory)

- **No relative imports anywhere** – enforce the import strategy above.
- **Repository root detection:** `repository.is_initialized()` only searches the **current working directory** (the user’s project root). Does not traverse parent directories.
- **Running directly:** Because `vcs.py` uses absolute sibling imports, it can be invoked with `python vcs/vcs.py` or `python ~/tools/vcs/vcs.py`. The test environment will run `python /workspace/vcs/vcs.py` and succeed.

### 8. Testing Strategy (unchanged)

Tests can spawn the CLI from a temporary directory containing the `.vcs` structure, using subprocess or pytest. All imports now work correctly.

---

With this revised plan, the import errors are eliminated. The tool starts reliably, and all version control features become accessible.