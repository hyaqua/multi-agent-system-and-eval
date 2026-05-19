# Revised Implementation Plan: Simplified Git-like Version Control

This plan addresses the review feedback regarding bugs in the `status`, `checkout`, and `switch` commands, and adds an improvement to clean up working tree files when switching branches. The source code for `repository.py` is updated; all other modules remain as originally specified.

---

## 0. Changes Summary

1. **`add` command now stages deletions** – When a file that is tracked (in HEAD or index) is missing from the working directory, `add` removes it from the index, effectively staging a deletion. This is necessary for the `status` command to correctly report staged deletions.

2. **`status` command correctly differentiates staged vs. unstaged deletions** – Files present in HEAD but absent from the index are shown as “deleted” under “Changes to be committed”. Files present in the index but missing from the working tree are shown as “deleted” under “Changes not staged for commit”. Removes the old ambiguous “Deleted files” block.

3. **`checkout` and `switch` update the staging index** – After restoring files to match a target commit, the index is rewritten to exactly mirror the commit’s manifest. This eliminates spurious changes in subsequent `status` calls.

4. **`checkout` and `switch` remove untracked working tree files not in the target commit** (optional but recommended) – When switching to a branch or a detached commit, any file that exists in the working directory but is not part of the target commit’s manifest is deleted, preventing leftover files from causing confusion.

---

## 1. Complete Source Code (Updated)

### 1.1 `constants.py` (unchanged)

```python
"""Path constants for the .vcs directory structure."""

VCS_DIR = ".vcs"
OBJECTS_DIR = "objects"
REFS_HEADS = "refs/heads"
HEAD_FILE = "HEAD"
INDEX_FILE = "index"
DEFAULT_BRANCH = "master"
```

### 1.2 `utils.py` (unchanged)

```python
"""Utility functions: hashing, object storage, binary detection, file scanning."""
import hashlib
import json
import os
import pathlib
from typing import Dict, Optional, Tuple


def hash_content(content: bytes) -> str:
    """Return SHA-1 hex digest of given bytes."""
    return hashlib.sha1(content).hexdigest()


def store_object(repo_root: pathlib.Path, obj_type: str, content: bytes) -> str:
    """Store a VCS object (blob, commit, etc.) and return its SHA-1 hash."""
    obj_hash = hash_content(content)
    obj_dir = repo_root / ".vcs" / "objects" / obj_hash[:2]
    obj_dir.mkdir(parents=True, exist_ok=True)
    obj_path = obj_dir / obj_hash[2:]
    obj_path.write_bytes(content)
    return obj_hash


def load_object(repo_root: pathlib.Path, obj_hash: str) -> Tuple[str, bytes]:
    """Read a VCS object and return (type, raw_content)."""
    obj_path = repo_root / ".vcs" / "objects" / obj_hash[:2] / obj_hash[2:]
    if not obj_path.exists():
        raise FileNotFoundError(f"Object {obj_hash} not found")
    data = obj_path.read_bytes()
    # The object format is: type + newline + payload
    newline = data.index(b'\n')
    obj_type = data[:newline].decode()
    payload = data[newline+1:]
    return obj_type, payload


def is_binary(path: pathlib.Path) -> bool:
    """Heuristic: a file is binary if it contains a null byte in the first 8 KB."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b'\x00' in chunk
    except Exception:
        return True


def get_working_files(repo_root: pathlib.Path) -> Dict[str, str]:
    """
    Walk the working directory (ignoring .vcs), read every file, and return
    a dictionary mapping relative path -> SHA-1 hash of its content.
    """
    file_map = {}
    vcs_dir = repo_root / ".vcs"
    for root, dirs, files in os.walk(repo_root):
        # Skip .vcs entirely
        if pathlib.Path(root) == vcs_dir or vcs_dir in pathlib.Path(root).parents:
            continue
        for name in files:
            full = pathlib.Path(root) / name
            rel = full.relative_to(repo_root).as_posix()
            content = full.read_bytes()
            file_map[rel] = hash_content(content)
    return file_map


def resolve_head(repo_root: pathlib.Path) -> Optional[str]:
    """
    Read HEAD and return the current commit hash.
    Returns None if there is no commit yet (empty repository).
    """
    head_path = repo_root / ".vcs" / "HEAD"
    if not head_path.exists():
        return None
    head_content = head_path.read_text().strip()
    if head_content.startswith("ref: "):
        ref_path = repo_root / ".vcs" / head_content[5:]
        if ref_path.exists():
            return ref_path.read_text().strip()
        else:
            return None
    else:
        # Detached HEAD
        return head_content
```

### 1.3 `repository.py` (revised – only this file is updated)

```python
"""Repository class implementing all VCS commands."""
import datetime
import difflib
import json
import pathlib
import shutil
import sys
import os
from typing import Dict, List, Optional, Tuple

# Local imports (assumes all files are in the same directory)
try:
    from constants import VCS_DIR, OBJECTS_DIR, REFS_HEADS, HEAD_FILE, INDEX_FILE, DEFAULT_BRANCH
    from utils import (
        hash_content, store_object, load_object, is_binary,
        get_working_files, resolve_head,
    )
except ImportError:
    # Fallback if executed from a different location; adjust as needed.
    import constants, utils
    VCS_DIR = constants.VCS_DIR
    OBJECTS_DIR = constants.OBJECTS_DIR
    REFS_HEADS = constants.REFS_HEADS
    HEAD_FILE = constants.HEAD_FILE
    INDEX_FILE = constants.INDEX_FILE
    DEFAULT_BRANCH = constants.DEFAULT_BRANCH
    hash_content = utils.hash_content
    store_object = utils.store_object
    load_object = utils.load_object
    is_binary = utils.is_binary
    get_working_files = utils.get_working_files
    resolve_head = utils.resolve_head


class Repository:
    def __init__(self, root: pathlib.Path):
        self.root = root.resolve()

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    @property
    def vcs_dir(self) -> pathlib.Path:
        return self.root / VCS_DIR

    @property
    def index_path(self) -> pathlib.Path:
        return self.vcs_dir / INDEX_FILE

    @property
    def head_path(self) -> pathlib.Path:
        return self.vcs_dir / HEAD_FILE

    def _read_index(self) -> Dict[str, str]:
        """Return the staging index (path -> blob hash)."""
        if not self.index_path.exists():
            return {}
        with open(self.index_path, "r") as f:
            return json.load(f)

    def _write_index(self, index: Dict[str, str]) -> None:
        with open(self.index_path, "w") as f:
            json.dump(index, f, indent=2)

    def _store_blob(self, file_path: pathlib.Path) -> str:
        """Read a file from the working directory and store it as a blob object."""
        content = file_path.read_bytes()
        blob_hash = store_object(self.root, "blob", content)
        return blob_hash

    def _update_head_to_hash(self, commit_hash: str):
        """Write a detached HEAD reference."""
        self.head_path.write_text(commit_hash)

    def _update_head_to_branch(self, branch_name: str):
        """Write a symbolic HEAD reference."""
        self.head_path.write_text(f"ref: {REFS_HEADS}/{branch_name}")

    def _get_branch_ref_path(self, branch_name: str) -> pathlib.Path:
        return self.vcs_dir / REFS_HEADS / branch_name

    def _read_branch_tip(self, branch_name: str) -> Optional[str]:
        """Return the commit hash pointed to by a branch, or None."""
        ref_path = self._get_branch_ref_path(branch_name)
        if not ref_path.exists():
            return None
        return ref_path.read_text().strip()

    def _write_branch_tip(self, branch_name: str, commit_hash: str):
        ref_path = self._get_branch_ref_path(branch_name)
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_text(commit_hash)

    def _get_current_branch_or_hash(self) -> Tuple[Optional[str], Optional[str]]:
        """Return (branch_name, commit_hash) from HEAD."""
        if not self.head_path.exists():
            return None, None
        head_content = self.head_path.read_text().strip()
        if head_content.startswith("ref: "):
            branch_ref = head_content[5:]
            # branch_ref is like "refs/heads/<name>"
            branch_name = branch_ref.split("/")[-1]
            commit_hash = self._read_branch_tip(branch_name)
            return branch_name, commit_hash
        else:
            return None, head_content  # detached HEAD

    def _resolve_commit_hash(self, short_hash: str) -> Optional[str]:
        """Resolve an abbreviated commit hash to a full hash."""
        if len(short_hash) == 40:
            obj_path = self.vcs_dir / OBJECTS_DIR / short_hash[:2] / short_hash[2:]
            return short_hash if obj_path.exists() else None
        prefix = short_hash[:2]
        remainder = short_hash[2:]
        parent_dir = self.vcs_dir / OBJECTS_DIR / prefix
        if not parent_dir.exists():
            return None
        candidates = []
        for entry in parent_dir.iterdir():
            if entry.name.startswith(remainder):
                candidates.append(prefix + entry.name)
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _get_head_manifest(self) -> Dict[str, str]:
        """Return the manifest of the HEAD commit, or empty dict."""
        head_hash = resolve_head(self.root)
        if not head_hash:
            return {}
        try:
            _, data = load_object(self.root, head_hash)
            commit_obj = json.loads(data.decode("utf-8"))
            return commit_obj.get("manifest", {})
        except Exception:
            return {}

    # ------------------------------------------------------------------ #
    #  Public commands
    # ------------------------------------------------------------------ #
    def init(self) -> None:
        """Initialize a new VCS repository."""
        if self.vcs_dir.exists():
            print(f"Reinitialized existing VCS repository in {self.root}")
            return
        (self.vcs_dir / OBJECTS_DIR).mkdir(parents=True)
        (self.vcs_dir / REFS_HEADS).mkdir(parents=True)
        self._update_head_to_branch(DEFAULT_BRANCH)
        self._write_index({})
        print(f"Initialized empty VCS repository in {self.root}")

    def add(self, file_paths: List[str]) -> None:
        """Stage files or deletions for the next commit."""
        index = self._read_index()
        head_manifest = self._get_head_manifest()

        for path_str in file_paths:
            file_path = self.root / path_str
            if file_path.exists() and file_path.is_file():
                # File exists – stage its content
                blob_hash = self._store_blob(file_path)
                index[path_str] = blob_hash
                print(f"Staged '{path_str}'")
            elif not file_path.exists():
                # File missing – stage a deletion if it is tracked
                if path_str in index or path_str in head_manifest:
                    # Remove from index to signal deletion
                    if path_str in index:
                        del index[path_str]
                    print(f"Staged deletion of '{path_str}'")
                else:
                    print(f"error: '{path_str}' is not tracked", file=sys.stderr)
            else:
                print(f"error: '{path_str}' is not a regular file", file=sys.stderr)
        self._write_index(index)

    def commit(self, message: str, author: str = "unknown") -> Optional[str]:
        """Create a commit containing the currently staged files."""
        index = self._read_index()
        # Allow empty commit only if there are staged deletions? For simplicity, still require something staged.
        if not index:
            print("nothing to commit", file=sys.stderr)
            return None

        parent_hash = resolve_head(self.root)
        manifest = dict(index)  # copy
        commit_data = {
            "parent": parent_hash,
            "author": author,
            "timestamp": datetime.datetime.now().isoformat(),
            "message": message,
            "manifest": manifest,
        }
        commit_bytes = json.dumps(commit_data, indent=2).encode("utf-8")
        commit_content = b"commit\n" + commit_bytes
        commit_hash = store_object(self.root, "commit", commit_content)

        branch_name, _ = self._get_current_branch_or_hash()
        if branch_name:
            self._write_branch_tip(branch_name, commit_hash)
        else:
            self._update_head_to_hash(commit_hash)

        self._write_index({})
        short = commit_hash[:7]
        print(f"[{branch_name or 'detached'} {short}] {message}")
        return commit_hash

    def status(self) -> None:
        """Show working tree status, including staged/unstaged deletions and untracked files."""
        index = self._read_index()
        head_manifest = self._get_head_manifest()
        working_files = get_working_files(self.root)

        all_paths = set(index.keys()) | set(head_manifest.keys()) | set(working_files.keys())

        staged_changes = []
        unstaged_changes = []
        untracked = []

        for path in sorted(all_paths):
            in_work = path in working_files
            in_index = path in index
            in_head = path in head_manifest

            work_hash = working_files.get(path)
            index_hash = index.get(path)
            head_hash = head_manifest.get(path)

            # 1. Staged changes (will be committed as is)
            if in_index:
                # File is staged
                if not in_work:
                    # Staged deletion (file removed from working tree, but still in index – shouldn't happen normally
                    # because we now handle deletions by removing from index. But keep safe.)
                    staged_changes.append(f"deleted:    {path}")
                elif not in_head:
                    staged_changes.append(f"new file:   {path}")
                elif index_hash != head_hash:
                    staged_changes.append(f"modified:   {path}")
            elif not in_work and in_head:
                # File in HEAD but not in index and missing from work => staged deletion
                staged_changes.append(f"deleted:    {path}")
            elif not in_index and not in_head and in_work:
                # Untracked file
                untracked.append(path)

            # 2. Unstaged changes (work tree differs from index or HEAD)
            if in_work and in_head and not in_index:
                # File tracked but not staged for commit
                if work_hash != head_hash:
                    unstaged_changes.append(f"modified:   {path}")
            elif in_work and in_index:
                # File staged, but maybe modified in work tree
                if work_hash != index_hash:
                    unstaged_changes.append(f"modified:   {path}")
            elif in_index and not in_work:
                # Index says file exists, but it's missing – unstaged deletion
                unstaged_changes.append(f"deleted:    {path}")

        if staged_changes:
            print("Changes to be committed:")
            for line in staged_changes:
                print(f"  {line}")
            print()
        if unstaged_changes:
            print("Changes not staged for commit:")
            for line in unstaged_changes:
                print(f"  {line}")
            print()
        if untracked:
            print("Untracked files:")
            for path in untracked:
                print(f"  {path}")
            print()
        if not (staged_changes or unstaged_changes or untracked):
            print("nothing to commit, working tree clean")

    def log(self) -> None:
        """Display the commit history."""
        current_hash = resolve_head(self.root)
        if not current_hash:
            print("No commits yet")
            return
        while current_hash:
            try:
                obj_type, content = load_object(self.root, current_hash)
                if obj_type != "commit":
                    break
                commit_obj = json.loads(content.decode("utf-8"))
                short = current_hash[:7]
                print(f"commit {short}")
                print(f"Author: {commit_obj['author']}")
                print(f"Date:   {commit_obj['timestamp']}")
                print()
                print(f"    {commit_obj['message']}")
                print()
                current_hash = commit_obj.get("parent")
            except Exception as e:
                print(f"error reading commit {current_hash}: {e}", file=sys.stderr)
                break

    def diff(self) -> None:
        """Show diffs between working directory and the last commit."""
        head_manifest = self._get_head_manifest()
        working_files = get_working_files(self.root)
        all_paths = set(head_manifest.keys()) | set(working_files.keys())

        for path in sorted(all_paths):
            in_work = path in working_files
            in_head = path in head_manifest

            if not in_work and not in_head:
                continue

            if in_work:
                file_path = self.root / path
                binary = is_binary(file_path)
            else:
                blob_hash = head_manifest[path]
                try:
                    _, blob_data = load_object(self.root, blob_hash)
                    binary = b'\x00' in blob_data[:8192]
                except Exception:
                    binary = True

            if binary:
                print(f"Binary files {path} differ")
                continue

            def get_lines(blob_hash):
                try:
                    _, data = load_object(self.root, blob_hash)
                    return data.decode("utf-8", errors="replace").splitlines(keepends=True)
                except Exception:
                    return []

            old_lines = get_lines(head_manifest[path]) if in_head else []
            new_lines = []
            if in_work:
                new_lines = (self.root / path).read_text(errors="replace").splitlines(keepends=True)

            diff_lines = difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
            for line in diff_lines:
                print(line, end="")
            if old_lines != new_lines:
                print("\n")

    def checkout(self, commit_hash: str) -> None:
        """Restore all files to the state of the specified commit (detached HEAD).
        Also updates the index to match, and removes files not in the commit."""
        full_hash = self._resolve_commit_hash(commit_hash)
        if not full_hash:
            print(f"error: pathspec '{commit_hash}' did not match any commit", file=sys.stderr)
            sys.exit(1)
        try:
            obj_type, content = load_object(self.root, full_hash)
            if obj_type != "commit":
                print(f"error: object {full_hash} is not a commit", file=sys.stderr)
                sys.exit(1)
            commit_obj = json.loads(content.decode("utf-8"))
            manifest = commit_obj["manifest"]
        except Exception as e:
            print(f"error: cannot load commit {full_hash}: {e}", file=sys.stderr)
            sys.exit(1)

        self._restore_commit_state(manifest)
        self._update_head_to_hash(full_hash)
        print(f"HEAD is now at {full_hash[:7]}")

    def branch(self, name: str) -> None:
        """Create a new branch at the current commit."""
        current_hash = resolve_head(self.root)
        if not current_hash:
            print("error: no commits yet, cannot create branch", file=sys.stderr)
            sys.exit(1)
        ref_path = self._get_branch_ref_path(name)
        if ref_path.exists():
            print(f"fatal: a branch named '{name}' already exists", file=sys.stderr)
            sys.exit(1)
        self._write_branch_tip(name, current_hash)
        print(f"Branch '{name}' created at {current_hash[:7]}")

    def switch(self, name: str) -> None:
        """Switch to an existing branch, restore its files, update index,
        and remove working tree files not in the target commit."""
        ref_path = self._get_branch_ref_path(name)
        if not ref_path.exists():
            print(f"error: branch '{name}' not found", file=sys.stderr)
            sys.exit(1)
        tip_hash = ref_path.read_text().strip()
        try:
            _, content = load_object(self.root, tip_hash)
            commit_obj = json.loads(content.decode("utf-8"))
            manifest = commit_obj["manifest"]
        except Exception as e:
            print(f"error: cannot load commit {tip_hash}: {e}", file=sys.stderr)
            sys.exit(1)

        self._restore_commit_state(manifest)
        self._update_head_to_branch(name)
        print(f"Switched to branch '{name}'")

    def _restore_commit_state(self, manifest: Dict[str, str]) -> None:
        """Helper for checkout/switch: write working tree files, remove excess files,
        and set the index to exactly the given manifest."""
        # Write all files from manifest
        for path, blob_hash in manifest.items():
            _, blob_data = load_object(self.root, blob_hash)
            dest = self.root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob_data)

        # Remove working tree files that are not in the manifest
        working_files = get_working_files(self.root)
        for path in working_files:
            if path not in manifest:
                (self.root / path).unlink(missing_ok=True)

        # Update index to match manifest
        self._write_index(dict(manifest))
```

### 1.4 `vcs.py` (unchanged)

```python
#!/usr/bin/env python3
"""Simplified Git-like version control – CLI entry point."""
import argparse
import os
import pathlib
import sys

# Ensure local modules are importable
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from repository import Repository
from constants import VCS_DIR


def find_repo_root() -> pathlib.Path:
    """Walk up from cwd until .vcs directory is found."""
    current = pathlib.Path.cwd()
    while True:
        if (current / VCS_DIR).is_dir():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding .vcs
            break
        current = parent
    print("fatal: not a VCS repository (or any of the parent directories): .vcs", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="vcs", description="Simple version control system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize a new repository")

    # add
    parser_add = subparsers.add_parser("add", help="Stage files or deletions for commit")
    parser_add.add_argument("files", nargs="+", help="Files to stage")

    # commit
    parser_commit = subparsers.add_parser("commit", help="Commit staged changes")
    parser_commit.add_argument("-m", "--message", required=True, help="Commit message")
    parser_commit.add_argument("--author", default="unknown", help="Author name")

    # status
    subparsers.add_parser("status", help="Show working tree status")

    # log
    subparsers.add_parser("log", help="Show commit history")

    # diff
    subparsers.add_parser("diff", help="Show changes between work tree and last commit")

    # checkout
    parser_checkout = subparsers.add_parser("checkout", help="Checkout a commit")
    parser_checkout.add_argument("commit", help="Commit hash (full or abbreviated)")

    # branch
    parser_branch = subparsers.add_parser("branch", help="Create a new branch")
    parser_branch.add_argument("name", help="Branch name")

    # switch
    parser_switch = subparsers.add_parser("switch", help="Switch to a branch")
    parser_switch.add_argument("name", help="Branch name")

    args = parser.parse_args()

    # init does not require a repo
    if args.command == "init":
        repo = Repository(pathlib.Path.cwd())
        repo.init()
        return

    # All other commands need a repository
    repo_root = find_repo_root()
    repo = Repository(repo_root)

    try:
        if args.command == "add":
            repo.add(args.files)
        elif args.command == "commit":
            repo.commit(args.message, args.author)
        elif args.command == "status":
            repo.status()
        elif args.command == "log":
            repo.log()
        elif args.command == "diff":
            repo.diff()
        elif args.command == "checkout":
            repo.checkout(args.commit)
        elif args.command == "branch":
            repo.branch(args.name)
        elif args.command == "switch":
            repo.switch(args.name)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## 2. Verification Steps

After creating/updating the four files, run these tests to confirm the fixes:

```bash
cd /home/user
python vcs.py --help

# Test staged deletions
mkdir testrepo && cd testrepo
python ../vcs.py init
echo "a" > a.txt
echo "b" > b.txt
python ../vcs.py add a.txt b.txt
python ../vcs.py commit -m "first commit"
rm a.txt
python ../vcs.py add a.txt          # Should stage deletion of a.txt
python ../vcs.py status             # Should show "deleted: a.txt" under "Changes to be committed"
python ../vcs.py commit -m "delete a"
python ../vcs.py log

# Test index update on checkout
echo "c" > c.txt
python ../vcs.py add c.txt
python ../vcs.py commit -m "add c"
hash=$(python ../vcs.py log | head -n 1 | cut -d' ' -f2)
python ../vcs.py checkout $hash     # Go back to previous commit
python ../vcs.py status             # Should show clean tree, no leftover files
# Check that c.txt is gone (removed by checkout)
ls c.txt 2>/dev/null || echo "c.txt removed as expected"

# Test index update on switch
cd ..
mkdir testrepo2 && cd testrepo2
python ../vcs.py init
echo "base" > base.txt
python ../vcs.py add base.txt
python ../vcs.py commit -m "base"
python ../vcs.py branch feature
python ../vcs.py switch feature
echo "feature work" > feat.txt
python ../vcs.py add feat.txt
python ../vcs.py commit -m "feature work"
python ../vcs.py switch master
python ../vcs.py status             # Should be clean, feat.txt removed
```

If all commands produce the expected outputs, the bugs are fixed and the optional improvement is in place.