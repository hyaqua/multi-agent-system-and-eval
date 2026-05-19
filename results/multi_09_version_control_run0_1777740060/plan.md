# Revised Implementation Plan: Simplified Git-like Version Control System (vcs)

> **Key fixes in this revision:**  
> - `status` correctly distinguishes new, modified, and identical staged files.  
> - `status` correctly reports unstaged modifications and deletions.  
> - **`commit` now explicitly prevents empty commits by comparing tree hash against parent before any storage or index clearing.**

---

### 1. Files to Create

- **`vcs.py`** – Main entry point containing all logic: CLI argument parsing, repository management, object storage, staging, committing, diffing, branching, and checkout. No external dependencies; uses only Python standard library modules (`os`, `sys`, `hashlib`, `datetime`, `argparse`, `difflib`, `shutil`, `json`).

### 2. Architecture

The system is structured as a single Python script with clear separation into classes and functions:

- **`Repository` class**  
  Manages the `.vcs` directory structure and provides high-level operations (`init`, `status`, `add`, `commit`, `log`, `diff`, `checkout`, `branch`, `switch`). It holds references to `ObjectStore`, `Index`, and the current HEAD.

- **`ObjectStore` class**  
  Handles content‑addressable storage of **blobs** (file contents), **trees** (snapshot file → blob mappings), and **commits**.  
  *Storage layout:*  
  `.vcs/objects/ab/cdef...` (two‑level directory based on SHA‑1 hash).  
  - Blob: raw file bytes.  
  - Tree: text with one `path:hash` line per file.  
  - Commit: text containing parent hash, tree hash, timestamp, message, author.

- **`Index` class**  
  Manages the staging area (`.vcs/index`). Stores a flat list of `<file_path> <blob_hash>` entries. Provides methods to add, clear, and read the index.

- **CLI**  
  Uses `argparse` to define subcommands (`init`, `status`, `add`, `commit`, `diff`, `log`, `checkout`, `branch`, `switch`). Each subcommand instantiates a `Repository` and calls the corresponding method. A decorator/helper ensures a repository exists (except `init`).

### 3. Implementation Order

1. **Project skeleton & `init`**  
   Create `vcs.py` with argument parsing, repository existence check, and `init` command that sets up `.vcs/objects/`, `.vcs/refs/heads/`, `HEAD` (pointing to `refs/heads/master`), and empty index.

2. **Object storage**  
   Implement `ObjectStore` with methods:
   - `store_blob(data) -> hash` – store raw bytes.
   - `store_tree(file_dict) -> hash` – serialize `{path: blob_hash}` as sorted `path:hash` lines.
   - `store_commit(parent, tree_hash, message, author) -> hash` – create commit text, hash it, store.
   - Retrieval: `get_blob(hash)`, `get_tree(hash)`, `get_commit(hash)`.  
   Use `hashlib.sha1` for all hashing.

3. **Index and staging (`add`)**  
   Implement `Index` class with functions to read/write `.vcs/index`.  
   `add` command: for each given file, compute its SHA‑1 content hash, store blob in object store if not present, and record `<file_path> <hash>` in index. Overwrites previous entry for the same path.

4. **`status` command (fully fixed)**  
   **Goal:** Show exactly which files are new, modified, or deleted, both staged and unstaged, without false positives.

   - Load HEAD commit tree (or empty dict if no commit) → `{path: blob_hash}` (“HEAD tree”).
   - Load index → `{path: staged_blob_hash}`.
   - Scan working directory (exclude `.vcs/`), compute SHA‑1 of each file → `{path: working_hash}`.

   **Staged changes (files that differ from HEAD):**
   ```
   for path, staged_hash in index_items:
       if path not in HEAD_tree:
           print("new file:", path)
       elif staged_hash != HEAD_tree[path]:
           print("modified:", path)
       # else: the staged hash matches HEAD – skip, nothing to show
   ```

   **Unstaged changes (tracked files, not staged, that differ from HEAD or are missing):**
   ```
   for path, head_hash in HEAD_tree_items:
       if path not in index:
           if path in working_dir:
               if working_dir[path] != head_hash:
                   print("modified:", path)
           else:
               print("deleted:", path)
   ```

   **Untracked files (present in working directory but neither in HEAD nor index):**
   ```
   for path in working_dir:
       if path not in HEAD_tree and path not in index:
           print("???", path)   # or simply print(path)
   ```

   This logic ensures:
   - Files identical between stage and HEAD produce no output.
   - New files are only reported when they are truly new in the index.
   - Modified files are correctly labeled whether they are staged or unstaged.
   - Deleted files (tracked, removed from working tree, not staged) are shown as “deleted”.

5. **`commit` command (with empty-commit guard)**  
   The commit operation must prevent the creation of a commit that changes nothing.  
   Steps:
   1. Build the new tree:
      - Start from the parent commit’s tree (if any) → `{path: blob_hash}`.
      - For every file in the parent tree:
        - If the file is in the **index**, use the staged blob hash.
        - Else, keep the parent blob hash (unstaged changes do not affect the commit).
        - Files in the parent tree that are missing from the working directory and **not** in the index are treated as deletions and removed from the new tree.
      - Add any path present in the index that was **not** in the parent tree (new files).
   2. **Compute the new tree’s SHA‑1 hash** by serializing the sorted dictionary **without storing it yet**.
   3. **Compare the new tree hash with the parent commit’s tree hash** (if a parent exists).
      - **If they are identical**, print exactly:  
        **`nothing to commit, working tree clean`**  
        Then exit the commit method **without** doing any of the following:
          - storing the tree,
          - creating the commit object,
          - updating the current branch reference,
          - clearing the staging index.
      - **If they are different**, proceed:
        - Store the tree object.
        - Create the commit object (with the parent, tree hash, message, timestamp).
        - Update the current branch reference to point to the new commit.
        - Clear the index (remove all entries from `.vcs/index`).

   This explicit guard ensures that a commit is only created when the repository state has actually changed.

6. **`log` command**  
   Traverse commit history starting from HEAD, printing hash, author, timestamp, message.

7. **`diff` command**  
   For each file in HEAD commit tree:
   - Retrieve its blob content and current working directory content.
   - If both are text (no null bytes, no decode errors), generate unified diff using `difflib.unified_diff`.  
   - If binary or cannot compare, output `Binary file <path> differs`.
   - Show added/deleted files as appropriate.

8. **`checkout` command**  
   Given a commit hash:
   - Read the target commit’s tree.
   - Determine tracked files in current HEAD commit (to know which files to delete).
   - Overwrite all files present in the target tree with their blob contents.
   - Delete any files that were tracked but are not in the target tree.
   - Update HEAD to detached mode (or switch to branch if specified; later `switch` will use this logic).

9. **Branching and switching**  
   `branch <name>`: create `.vcs/refs/heads/<name>` pointing to current HEAD commit.
   `switch <name>`: update `HEAD` to `ref: refs/heads/<name>`, then perform a `checkout` to that branch’s tip commit (using the same file replacement logic). Overwrites working directory without warning (simplified).

### 4. Libraries Needed

- **Standard library only**: `os`, `sys`, `hashlib`, `datetime`, `argparse`, `difflib`, `shutil`, `json` (optional for structured commit metadata, but plain text is sufficient). No external dependencies.

### 5. Additional Clean‑up

- Remove any unused imports (e.g., `shutil`, `json`, `fnmatch`) if they are not required.
- Verify that after fixing `status` and `commit`, the test suite passes with the expected output (no `new file` for unchanged staged files, proper missing/deleted notifications, and no empty commits).