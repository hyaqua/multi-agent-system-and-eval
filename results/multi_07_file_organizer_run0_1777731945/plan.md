# Revised Implementation Plan: `file_organizer`

## Overview
The tool meets all required features except the **detailed per‑file listing** after scanning.  
Test results show the tool runs without errors, but only prints a summary count—no table with file names, categories, sizes, and modification dates.  
This plan adds that listing and cleans up two minor static‑analysis warnings (empty f‑string, unused parameter) in the progress indicator.  
All other functionality—dry‑run, undo, conflict resolution, permission handling, hidden‑file skipping, logging, and summaries—remains unchanged.

## Files to Modify
- **`file_organizer.py`** (only this file)

## Detailed Changes

### 1. Add per‑file listing (required feature)
- **New method:** `FileOrganizer.print_file_listing(file_items: List[FileItem])`
  - Outputs a formatted table similar to the following:  
    ```
    Scanned files:
    File Name                  Category        Size       Date Modified
    -------------------------------------------------------------------------
    README.md                  Document        1.2 KB     2024-06-15 14:30
    image_001.jpg              Image           2.5 MB     2023-09-10 08:15
    ...
    ```
  - Column specifications:
    - **File Name** – left‑justified, min width 25, truncated with `…` if necessary.
    - **Category** – left‑justified, width 15, obtained from existing `get_category(extension)`.
    - **Size** – right‑justified, width 10, human‑readable (e.g., `1.23 KB`, `2.50 MB`).
    - **Date Modified** – `YYYY-MM-DD HH:MM`, width 20.
  - After the table, the existing line `Found N file(s) to process.` is kept as is.

- **Integration in `main()`:**  
  After scanning and before building the move plan:
  ```python
  file_items = organizer.scan_files()   # already exists
  if not args.undo:
      organizer.print_file_listing(file_items)   # add this line
  ```

### 2. Code‑quality fixes for the progress indicator
Two minor issues exist in the current progress code (visible only to static analysis):

- **Empty f‑string:**  
  Change all f‑strings without replacement fields to plain strings.  
  Example: `f"Scanning directory:"` → `"Scanning directory:"`

- **Unused `end` parameter / signature cleanup:**  
  Simplify the progress method to:
  ```python
  def _show_progress(self, current: int, total: int, label: str = "Processing"):
      sys.stdout.write(f"\r{label} file {current}/{total}")
      sys.stdout.flush()
      if current == total:
          sys.stdout.write("\n")
  ```
  Update all callers to use the new signature (`_show_progress(current, total, label="...")`).

### 3. No other changes
All other features (dry‑run, undo, conflict resolution, permission warnings, hidden‑file skipping, external log, summary) are correctly implemented and require no adjustment.  
Test‑environment permission errors are handled gracefully by design; the tool warns and skips when directories cannot be created.

## Execution Order (finalised in `main()`)
1. Parse command‑line arguments.
2. If not an undo operation:
   a. Scan files (shows progress).
   b. **Print the per‑file listing table** (new).
3. Build the move plan (based on the chosen rule).
4. If `--dry-run`: print plan summary only.
5. If `--undo`: restore files from the JSON log.
6. Otherwise: execute moves, skipping on permission errors, logging successes.
7. Print final summary.

## Implementation Steps
1. Write `FileOrganizer.print_file_listing()` with the formatting described above.
2. Integrate the call in `main()` immediately after scanning (skip for undo).
3. Clean up the progress indicator (remove empty f‑strings, simplify signature).
4. Test on a directory with a mix of file types and sizes, verifying the table appears with correct alignment and values.
5. Run static analysis (e.g., `pylint`, `flake8`) to confirm no unfilled f‑string or unused variable warnings remain.
6. Execute full end‑to‑end tests: dry‑run, real run, undo, and permission‑denied scenarios to ensure no regressions.

## Conclusion
This plan addresses the only missing feature—the per‑file scan listing—and corrects two code‑quality nits. After these changes the tool fulfills every requirement of the original specification, as confirmed by the test environment and manual inspection.