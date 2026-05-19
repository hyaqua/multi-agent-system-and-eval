# File Organizer Implementation Plan (Revised)

This revised plan addresses the feedback from the initial review: the per‑file table (type, size, modification date) was missing from the implementation, and an unused `mode_label` variable must be removed. The plan now makes these requirements explicit and tightens the integration of the table output. All other working features remain unchanged.

---

## Overview

The tool is a single Python script that accepts a target directory, scans it, **always prints a full listing of every file (with type/category, human‑readable size, and modification date)**, then organises files according to a chosen rule (extension category, date, or size). It supports dry‑run, logging, and undo. The revised plan ensures the per‑file table appears as the first user‑visible output in every normal run.

---

## 1. Files to Create

- **`file_organizer.py`** – Single self-contained script. All logic: argument parsing, scanning, mandatory per‑file table, organisation, conflict resolution, dry‑run, logging, and undo.

---

## 2. Architecture

### CLI layer
- `argparse` with:
  - `directory` – positional, required.
  - `--by-date` – mutually exclusive with `--by-size`.
  - `--by-size` – mutually exclusive with `--by-date`.
  - `--dry-run` – optional flag.
  - `--undo` – optional flag (takes precedence, skips scanning).

### Program flow (critical order)
1. Parse arguments. If `--undo`, skip scanning and go to undo.
2. **Scan** target directory → list of `FileInfo` objects.
3. **Assign extension category** to every file (needed for the table’s “Type” column).
4. **📋 Print the per‑file table** – this is mandatory, always shown immediately after scanning (except for `--undo`). It lists **Name**, **Type** (category), **Size**, and **Modified** for every non‑hidden file.
5. If not `--undo`:
   - Select organisation rule: default (by category), `--by-date`, or `--by-size`.
   - Perform moves (or simulate in dry‑run), resolve conflicts, log operations.
6. Print a **summary** table showing how many files go to each destination.
7. If `--undo`:
   - Read the log, reverse the last batch, update log, print its own summary.

### Core functions

- **`FileInfo`** dataclass: `name`, `path`, `extension`, `category`, `size` (bytes), `mtime` (float).
- **`scan_directory(target)`** – lists only regular, non‑hidden files; catches `PermissionError` and prints warnings.
- **`categorize_by_extension(files)`** – sets `category` field (Images, Documents, Audio, Video, Code, Other) based on file extension.
- **`print_file_table(files)`** – prints the required per‑file table with four columns.
- **`categorize_by_date(files)`** – returns destination paths `year/month/filename`.
- **`categorize_by_size(files)`** – thresholds: Small < 1 MiB, Medium 1–100 MiB, Large > 100 MiB.
- **`resolve_conflict(dest_path)`** – appends `_1`, `_2`, … until free.
- **`move_file(src, dest, dry_run, log_entries)`** – moves or simulates; logs entry on success.
- **`perform_organization(files, categorizer, dry_run)`** – iterates files, shows progress, calls `move_file`.
- **`log_batch(batch_id, entries, target)`** – appends batch to `.file_organizer_log.json`.
- **`undo_last(target)`** – reads log, finds latest batch, moves back, removes batch, prints summary.
- **`human_readable_size(bytes)`** – helper.

### Log format
- Hidden JSON file `.file_organizer_log.json` in target.
- Array of objects:
  ```json
  {
    "batch_id": "20250314123045",
    "source": "/path/src/file.txt",
    "destination": "/path/dst/file.txt",
    "timestamp": "2025-03-14 12:30:45"
  }
  ```

---

## 3. Implementation Order

1. **Command‑line parsing** – ensure `directory` is required; test with `--undo` to bypass scanning.
2. **Directory scanning** – build `FileInfo` list; skip hidden entries; handle permission errors.
3. **Extension categorisation** – must run immediately after scanning, before any output.
4. **📋 Per‑file table** – `print_file_table(files)` is called right after categorisation.  
   *This step was missing in the original implementation; now it is explicitly enforced.*
5. **Date and size categorisation functions** – only used when respective flags are set.
6. **Conflict resolution** – based on `os.path.exists`.
7. **Move and logging** – move files or simulate; create log entries.
8. **Progress indicator** – if total files > 20, update every 10 files.
9. **Summary** – count by destination and print.
10. **Undo** – read log, reverse, print summary.
11. **Cleanup** – remove any unused imports or variables (specifically, **no `mode_label` variable shall exist**).

---

## 4. Libraries

- `argparse`, `pathlib`, `os`, `shutil`, `json`, `datetime`, `sys` – all standard library.
- No external dependencies. Ensure that `time` is not imported (it is not needed for the simple progress indicator).

---

## 5. Feature Implementation Details

### Accept target directory
- Positional argument; validate with `os.path.isdir`.

### Per‑file listing (critical addition)
- **Scan**: iterate with `pathlib.Path(target).iterdir()`, skip names starting with `.`, collect file stats.
- **Table**: Always displayed after scanning (except `--undo`).  
  Format example:
  ```
  Scanned 5 files in /home/user/docs:
  Name                    Type         Size      Modified
  --------------------------------------------------------
  report.pdf              Documents    120.5 kB  2025-03-10 09:15
  photo.jpg               Images       2.1 MB    2025-03-12 14:22
  …
  ```
- **Columns**:
  - **Name** – base filename.
  - **Type** – the `category` assigned by `categorize_by_extension`.
  - **Size** – human‑readable (e.g., `2.3 MB`).
  - **Modified** – `yyyy-mm-dd HH:MM` from `datetime.fromtimestamp`.
- This fulfills the specification’s listing requirement and must be implemented exactly as described.

### Organise by extension (default)
- Destination: `<target>/<category>/<filename>`.

### Organise by date (`--by-date`)
- Destination: `<target>/<year>/<month>/<filename>`.

### Organise by size (`--by-size`)
- Destination: `<target>/Small/`, `Medium/`, `Large/`.

### Dry‑run mode
- `--dry-run` avoids any filesystem changes and logging; prints simulated moves.

### Summary display
- After all moves (or dry‑run), print a table of counts per destination.

### Filename conflicts
- `resolve_conflict` appends `_N` before the extension.

### JSON logging
- Append operations to `.file_organizer_log.json`. Undo reads from this file.

### Undo command
- `--undo` must not scan; it reads the log, moves files back, and prints its own summary.

### Skip hidden files
- Ignore any entry whose name begins with `.`.

### Permission errors
- Catch `PermissionError`, print a warning to stderr, and skip the file.

### Progress indicator
- Inside `perform_organization`, print a moving counter when files > 20.

### Code cleanliness (revised)
- **Remove any unused variable, especially `mode_label`.** The final script must pass a basic lint check with no dead variables or unused imports.

---

## 6. Test Considerations

- Running `file_organizer.py` without arguments must exit with code 2 and show usage. This is expected and not a bug.
- The per‑file table must appear in both normal and dry‑run modes before any organisation summary.
- The undo command prints its own summary but no per‑file table.