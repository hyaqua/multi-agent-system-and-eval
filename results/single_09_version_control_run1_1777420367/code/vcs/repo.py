"""Core repository operations for the VCS system."""

import os
import sys
import json
import hashlib
import shutil
import time
import difflib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set


def find_repo_root() -> Optional[Path]:
    """Walk up from cwd to find the .vcs directory."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".vcs").is_dir():
            return parent
    return None


def get_author() -> str:
    """Get the author from environment variables."""
    for var in ("VCS_AUTHOR", "USER", "USERNAME", "LOGNAME"):
        val = os.environ.get(var)
        if val:
            return val
    return "unknown"


class Repository:
    """A Git-like version control repository."""

    def __init__(self, root: Path):
        self.root = root
        self.vcs_dir = root / ".vcs"
        self.objects_dir = self.vcs_dir / "objects"
        self.refs_heads_dir = self.vcs_dir / "refs" / "heads"
        self.head_file = self.vcs_dir / "HEAD"
        self.index_file = self.vcs_dir / "index"

    # ------------------------------------------------------------------ #
    #  Initialization
    # ------------------------------------------------------------------ #

    @classmethod
    def init(cls, path: Path = None) -> "Repository":
        """Initialize a new repository."""
        root = path or Path.cwd()
        vcs_dir = root / ".vcs"
        if vcs_dir.exists():
            print(f"Repository already exists at {root}")
            sys.exit(1)

        vcs_dir.mkdir()
        (vcs_dir / "objects").mkdir()
        (vcs_dir / "refs" / "heads").mkdir(parents=True)
        (vcs_dir / "HEAD").write_text("ref: refs/heads/main\n")
        (vcs_dir / "index").write_text("{}")

        print(f"Initialized empty VCS repository in {vcs_dir}")
        return cls(root)

    @classmethod
    def load(cls) -> "Repository":
        """Load an existing repository, or exit with error."""
        root = find_repo_root()
        if root is None:
            print("error: not a VCS repository (or any parent directory)")
            print("  run 'vcs init' to create one")
            sys.exit(1)
        return cls(root)

    # ------------------------------------------------------------------ #
    #  Object storage helpers
    # ------------------------------------------------------------------ #

    def _hash_content(self, content: bytes, obj_type: str) -> str:
        """Compute SHA-1 hash for an object (Git-style)."""
        header = f"{obj_type} {len(content)}\0".encode("utf-8")
        return hashlib.sha1(header + content).hexdigest()

    def _store_object(self, content: bytes, obj_type: str) -> str:
        """Store content as an object, return its hash."""
        obj_hash = self._hash_content(content, obj_type)
        if self._object_exists(obj_hash):
            return obj_hash
        prefix = obj_hash[:2]
        suffix = obj_hash[2:]
        obj_dir = self.objects_dir / prefix
        obj_dir.mkdir(exist_ok=True)
        (obj_dir / suffix).write_bytes(content)
        return obj_hash

    def _object_exists(self, obj_hash: str) -> bool:
        """Check if an object already exists in the store."""
        path = self.objects_dir / obj_hash[:2] / obj_hash[2:]
        return path.exists()

    def _read_object(self, obj_hash: str) -> bytes:
        """Read raw object content by hash."""
        path = self.objects_dir / obj_hash[:2] / obj_hash[2:]
        if not path.exists():
            print(f"error: object {obj_hash[:7]} not found")
            sys.exit(1)
        return path.read_bytes()

    # ------------------------------------------------------------------ #
    #  Blob operations
    # ------------------------------------------------------------------ #

    def _store_blob(self, filepath: Path) -> str:
        """Store a file's content as a blob, return its hash."""
        content = filepath.read_bytes()
        return self._store_object(content, "blob")

    def _get_blob_content(self, blob_hash: str) -> bytes:
        """Retrieve blob content by hash."""
        return self._read_object(blob_hash)

    # ------------------------------------------------------------------ #
    #  Tree operations
    # ------------------------------------------------------------------ #

    def _store_tree(self, tree_data: Dict[str, str]) -> str:
        """Store a tree object (filename -> blob_hash mapping)."""
        content = json.dumps(tree_data, sort_keys=True).encode("utf-8")
        return self._store_object(content, "tree")

    def _get_tree(self, tree_hash: str) -> Dict[str, str]:
        """Retrieve and parse a tree object by hash."""
        content = self._read_object(tree_hash)
        return json.loads(content.decode("utf-8"))

    # ------------------------------------------------------------------ #
    #  Commit operations
    # ------------------------------------------------------------------ #

    def _store_commit(self, tree_hash: str, parent_hash: Optional[str],
                      message: str, author: str) -> str:
        """Store a commit object, return its hash."""
        commit_data = {
            "tree": tree_hash,
            "parent": parent_hash,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "author": author,
        }
        content = json.dumps(commit_data, sort_keys=True).encode("utf-8")
        return self._store_object(content, "commit")

    def _get_commit(self, commit_hash: str) -> dict:
        """Retrieve and parse a commit object."""
        content = self._read_object(commit_hash)
        return json.loads(content.decode("utf-8"))

    # ------------------------------------------------------------------ #
    #  HEAD / branch resolution
    # ------------------------------------------------------------------ #

    def _read_head_raw(self) -> str:
        """Read the raw HEAD file content."""
        return self.head_file.read_text().strip()

    def _write_head_raw(self, value: str):
        """Write raw content to HEAD."""
        self.head_file.write_text(value + "\n")

    def _resolve_head(self) -> Optional[str]:
        """Resolve HEAD to a commit hash, or None if no commits yet."""
        raw = self._read_head_raw()
        if raw.startswith("ref: "):
            ref_path = raw[5:]
            branch_file = self.vcs_dir / ref_path
            if branch_file.exists():
                return branch_file.read_text().strip()
            return None
        else:
            # Detached HEAD – raw is the commit hash
            return raw if raw else None

    def _get_current_branch(self) -> Optional[str]:
        """Return the current branch name, or None if detached."""
        raw = self._read_head_raw()
        if raw.startswith("ref: refs/heads/"):
            return raw[16:]
        return None

    def _set_branch_commit(self, branch_name: str, commit_hash: str):
        """Update a branch reference to point to a commit."""
        branch_file = self.refs_heads_dir / branch_name
        branch_file.write_text(commit_hash + "\n")

    def _get_branch_commit(self, branch_name: str) -> Optional[str]:
        """Get the commit hash a branch points to."""
        branch_file = self.refs_heads_dir / branch_name
        if branch_file.exists():
            return branch_file.read_text().strip()
        return None

    def _list_branches(self) -> List[str]:
        """List all branch names."""
        if not self.refs_heads_dir.exists():
            return []
        return sorted([p.name for p in self.refs_heads_dir.iterdir()])

    # ------------------------------------------------------------------ #
    #  Index (staging area) helpers
    # ------------------------------------------------------------------ #

    def _read_index(self) -> Dict[str, Optional[str]]:
        """Read staging index.  Value None means 'delete this file'."""
        if not self.index_file.exists():
            return {}
        return json.loads(self.index_file.read_text())

    def _write_index(self, index: Dict[str, Optional[str]]):
        """Write staging index."""
        self.index_file.write_text(json.dumps(index, sort_keys=True, indent=2))

    # ------------------------------------------------------------------ #
    #  Working directory helpers
    # ------------------------------------------------------------------ #

    def _scan_working_dir(self) -> List[Path]:
        """Return relative paths of all files in working directory (excluding .vcs)."""
        files = []
        for entry in self.root.rglob("*"):
            if entry.is_file():
                rel = entry.relative_to(self.root)
                # Skip anything inside .vcs
                if rel.parts and rel.parts[0] == ".vcs":
                    continue
                files.append(rel)
        return sorted(files)

    @staticmethod
    def _is_binary(content: bytes) -> bool:
        """Heuristic: check for null bytes or invalid UTF-8."""
        if b"\x00" in content[:8000]:
            return True
        try:
            content[:8000].decode("utf-8")
            return False
        except UnicodeDecodeError:
            return True

    # ================================================================== #
    #  Public commands
    # ================================================================== #

    # ------------------------------------------------------------------ #
    #  status
    # ------------------------------------------------------------------ #

    def status(self):
        """Show working-tree status."""
        head_commit = self._resolve_head()
        head_tree: Dict[str, str] = {}
        if head_commit:
            commit = self._get_commit(head_commit)
            head_tree = self._get_tree(commit["tree"])

        index = self._read_index()
        working_files = self._scan_working_dir()
        working_set: Set[str] = {str(f) for f in working_files}

        staged_new: List[str] = []
        staged_modified: List[str] = []
        staged_deleted: List[str] = []
        not_staged_modified: List[str] = []
        not_staged_deleted: List[str] = []
        untracked: List[str] = []

        # Files in the index (staged)
        for fpath, blob_hash in index.items():
            if blob_hash is None:
                # Staged for deletion
                staged_deleted.append(fpath)
            else:
                if fpath not in head_tree:
                    staged_new.append(fpath)
                elif head_tree[fpath] != blob_hash:
                    staged_modified.append(fpath)

            # Check if working dir differs from staged version
            abs_path = self.root / fpath
            if blob_hash is not None and abs_path.exists():
                current_hash = self._store_blob(abs_path)
                if current_hash != blob_hash:
                    not_staged_modified.append(fpath)

        # Files in HEAD tree
        for fpath, blob_hash in head_tree.items():
            if fpath in index:
                continue  # already handled as staged
            abs_path = self.root / fpath
            if not abs_path.exists():
                not_staged_deleted.append(fpath)
            else:
                current_hash = self._store_blob(abs_path)
                if current_hash != blob_hash:
                    not_staged_modified.append(fpath)

        # Untracked files (not in HEAD, not in index)
        for rel_path in working_files:
            sp = str(rel_path)
            if sp not in head_tree and sp not in index:
                untracked.append(sp)

        # Check if on a branch
        branch = self._get_current_branch()
        if branch:
            print(f"On branch {branch}")
        else:
            hh = head_commit[:7] if head_commit else "none"
            print(f"HEAD detached at {hh}")

        if not head_commit and not index:
            print("\nNo commits yet")
            if untracked:
                print("\nUntracked files:")
                print("  (use 'vcs add <file>...' to include in what will be committed)")
                for f in untracked:
                    print(f"        {f}")
            return

        anything = False

        if staged_new or staged_modified or staged_deleted:
            anything = True
            print("\nChanges to be committed:")
            print("  (use 'vcs commit -m \"...\"' to commit)")
            for f in staged_new:
                print(f"        new file:   {f}")
            for f in staged_modified:
                print(f"        modified:   {f}")
            for f in staged_deleted:
                print(f"        deleted:    {f}")

        if not_staged_modified or not_staged_deleted:
            anything = True
            print("\nChanges not staged for commit:")
            print("  (use 'vcs add <file>...' to update what will be committed)")
            for f in not_staged_modified:
                print(f"        modified:   {f}")
            for f in not_staged_deleted:
                print(f"        deleted:    {f}")

        if untracked:
            anything = True
            print("\nUntracked files:")
            print("  (use 'vcs add <file>...' to include in what will be committed)")
            for f in untracked:
                print(f"        {f}")

        if not anything:
            print("nothing to commit, working tree clean")

    # ------------------------------------------------------------------ #
    #  add
    # ------------------------------------------------------------------ #

    def add(self, filepaths: List[str]):
        """Stage specific files for the next commit."""
        index = self._read_index()
        head_commit = self._resolve_head()
        head_tree: Dict[str, str] = {}
        if head_commit:
            head_tree = self._get_tree(self._get_commit(head_commit)["tree"])

        for fp in filepaths:
            abs_path = self.root / fp
            if abs_path.exists() and abs_path.is_file():
                # Stage the current content
                blob_hash = self._store_blob(abs_path)
                index[fp] = blob_hash
                print(f"staged: {fp}")
            elif fp in head_tree or fp in index:
                # File doesn't exist but is tracked – stage deletion
                index[fp] = None
                print(f"staged deletion: {fp}")
            else:
                print(f"error: '{fp}' did not match any files")
                sys.exit(1)

        self._write_index(index)

    # ------------------------------------------------------------------ #
    #  commit
    # ------------------------------------------------------------------ #

    def commit(self, message: str):
        """Create a new commit from staged changes."""
        if not message:
            print("error: commit message required (use -m)")
            sys.exit(1)

        index = self._read_index()
        if not index:
            print("error: nothing to commit (use 'vcs add' to stage files)")
            sys.exit(1)

        parent_hash = self._resolve_head()

        # Build new tree: start from parent tree, apply index changes
        if parent_hash:
            parent_commit = self._get_commit(parent_hash)
            tree = self._get_tree(parent_commit["tree"])
        else:
            tree = {}

        for fpath, blob_hash in index.items():
            if blob_hash is None:
                # Deletion
                tree.pop(fpath, None)
            else:
                tree[fpath] = blob_hash

        tree_hash = self._store_tree(tree)
        author = get_author()
        commit_hash = self._store_commit(tree_hash, parent_hash, message, author)

        # Update HEAD
        branch = self._get_current_branch()
        if branch:
            self._set_branch_commit(branch, commit_hash)
        else:
            self._write_head_raw(commit_hash)

        # Clear index
        self._write_index({})

        print(f"[{commit_hash[:7]}] {message}")

    # ------------------------------------------------------------------ #
    #  log
    # ------------------------------------------------------------------ #

    def log(self, max_count: int = 0):
        """Display commit history."""
        commit_hash = self._resolve_head()
        if commit_hash is None:
            print("error: no commits yet")
            return

        count = 0
        while commit_hash:
            commit = self._get_commit(commit_hash)
            ts = commit["timestamp"]
            # Make timestamp more readable
            try:
                dt = datetime.fromisoformat(ts)
                ts_display = dt.strftime("%Y-%m-%d %H:%M:%S %z")
            except Exception:
                ts_display = ts

            print(f"commit {commit_hash}")
            print(f"Author: {commit['author']}")
            print(f"Date:   {ts_display}")
            print(f"\n    {commit['message']}\n")

            count += 1
            if max_count > 0 and count >= max_count:
                break

            parent = commit.get("parent")
            if parent:
                commit_hash = parent
            else:
                break

    # ------------------------------------------------------------------ #
    #  diff
    # ------------------------------------------------------------------ #

    def diff(self):
        """Show line-by-line differences between working dir and last commit."""
        head_commit = self._resolve_head()
        if head_commit is None:
            print("error: no commits to diff against")
            return

        commit = self._get_commit(head_commit)
        head_tree = self._get_tree(commit["tree"])

        working_files = self._scan_working_dir()
        working_set: Set[str] = {str(f) for f in working_files}

        all_files = set(head_tree.keys()) | working_set
        found_diff = False

        for fpath in sorted(all_files):
            abs_path = self.root / fpath

            in_commit = fpath in head_tree
            in_working = fpath in working_set

            if in_commit and in_working:
                # Both exist – compare
                commit_blob = head_tree[fpath]
                current_blob = self._store_blob(abs_path)
                if commit_blob == current_blob:
                    continue  # unchanged

                old_content = self._get_blob_content(commit_blob)
                new_content = abs_path.read_bytes()

                if self._is_binary(old_content) or self._is_binary(new_content):
                    found_diff = True
                    print(f"diff --vcs a/{fpath} b/{fpath}")
                    print(f"Binary files differ")
                    print()
                    continue

                found_diff = True
                old_lines = old_content.decode("utf-8", errors="replace").splitlines(keepends=True)
                new_lines = new_content.decode("utf-8", errors="replace").splitlines(keepends=True)

                print(f"diff --vcs a/{fpath} b/{fpath}")
                diff_lines = list(difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"a/{fpath}",
                    tofile=f"b/{fpath}",
                    lineterm="",
                ))
                for line in diff_lines:
                    print(line)
                print()

            elif in_commit and not in_working:
                # Deleted
                found_diff = True
                commit_blob = head_tree[fpath]
                old_content = self._get_blob_content(commit_blob)
                if self._is_binary(old_content):
                    print(f"diff --vcs a/{fpath} /dev/null")
                    print(f"Binary file {fpath} deleted")
                    print()
                    continue

                old_lines = old_content.decode("utf-8", errors="replace").splitlines(keepends=True)
                print(f"diff --vcs a/{fpath} /dev/null")
                diff_lines = list(difflib.unified_diff(
                    old_lines, [],
                    fromfile=f"a/{fpath}",
                    tofile="/dev/null",
                    lineterm="",
                ))
                for line in diff_lines:
                    print(line)
                print()

            elif not in_commit and in_working:
                # New file
                found_diff = True
                new_content = abs_path.read_bytes()
                if self._is_binary(new_content):
                    print(f"diff --vcs /dev/null b/{fpath}")
                    print(f"Binary file {fpath} added")
                    print()
                    continue

                new_lines = new_content.decode("utf-8", errors="replace").splitlines(keepends=True)
                print(f"diff --vcs /dev/null b/{fpath}")
                diff_lines = list(difflib.unified_diff(
                    [], new_lines,
                    fromfile="/dev/null",
                    tofile=f"b/{fpath}",
                    lineterm="",
                ))
                for line in diff_lines:
                    print(line)
                print()

        if not found_diff:
            print("working tree clean (no differences from last commit)")

    # ------------------------------------------------------------------ #
    #  checkout
    # ------------------------------------------------------------------ #

    def checkout(self, commit_hash: str):
        """Restore all files to the state of a specific commit."""
        # Resolve abbreviated hash
        full_hash = self._resolve_hash(commit_hash)
        commit = self._get_commit(full_hash)
        tree = self._get_tree(commit["tree"])

        # Get current HEAD tree for cleanup
        current_head = self._resolve_head()
        current_tree: Dict[str, str] = {}
        if current_head:
            current_tree = self._get_tree(self._get_commit(current_head)["tree"])

        # Write files from the target tree
        for fpath, blob_hash in tree.items():
            content = self._get_blob_content(blob_hash)
            abs_path = self.root / fpath
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(content)

        # Remove files that were tracked but are not in target tree
        for fpath in current_tree:
            if fpath not in tree:
                abs_path = self.root / fpath
                if abs_path.exists():
                    abs_path.unlink()

        # Update HEAD (detached)
        self._write_head_raw(full_hash)

        # Clear index
        self._write_index({})

        print(f"Checked out commit {full_hash[:7]}")
        print(f"HEAD is now at {full_hash[:7]} {commit['message']}")

    def _resolve_hash(self, short_hash: str) -> str:
        """Resolve an abbreviated hash to a full hash by scanning objects."""
        if len(short_hash) == 40 and self._object_exists(short_hash):
            return short_hash

        candidates = []
        for prefix_dir in self.objects_dir.iterdir():
            if not prefix_dir.is_dir():
                continue
            for obj_file in prefix_dir.iterdir():
                full = prefix_dir.name + obj_file.name
                if full.startswith(short_hash):
                    candidates.append(full)

        if len(candidates) == 0:
            print(f"error: no object matching '{short_hash}' found")
            sys.exit(1)
        elif len(candidates) > 1:
            print(f"error: ambiguous hash '{short_hash}' – {len(candidates)} matches")
            sys.exit(1)

        return candidates[0]

    # ------------------------------------------------------------------ #
    #  branch
    # ------------------------------------------------------------------ #

    def branch(self, name: str = None, list_branches: bool = False,
               delete: str = None):
        """Create, list, or delete branches."""
        if delete:
            branch_file = self.refs_heads_dir / delete
            if not branch_file.exists():
                print(f"error: branch '{delete}' not found")
                sys.exit(1)
            current = self._get_current_branch()
            if current == delete:
                print(f"error: cannot delete branch '{delete}' – you are on it")
                sys.exit(1)
            branch_file.unlink()
            print(f"Deleted branch '{delete}'")
            return

        if list_branches or name is None:
            branches = self._list_branches()
            current = self._get_current_branch()
            if not branches:
                print("no branches")
                return
            for b in branches:
                prefix = "* " if b == current else "  "
                print(f"{prefix}{b}")
            return

        # Create a new branch
        branch_file = self.refs_heads_dir / name
        if branch_file.exists():
            print(f"error: branch '{name}' already exists")
            sys.exit(1)

        head_commit = self._resolve_head()
        if head_commit is None:
            print("error: no commits yet – cannot create branch")
            sys.exit(1)

        branch_file.write_text(head_commit + "\n")
        print(f"Created branch '{name}' at {head_commit[:7]}")

    # ------------------------------------------------------------------ #
    #  switch
    # ------------------------------------------------------------------ #

    def switch(self, name: str):
        """Switch to a different branch."""
        branch_file = self.refs_heads_dir / name
        if not branch_file.exists():
            print(f"error: branch '{name}' not found")
            sys.exit(1)

        target_commit = branch_file.read_text().strip()
        current_head = self._resolve_head()

        # Get trees
        target_tree = self._get_tree(self._get_commit(target_commit)["tree"])
        current_tree: Dict[str, str] = {}
        if current_head:
            current_tree = self._get_tree(self._get_commit(current_head)["tree"])

        # Write files from target tree
        for fpath, blob_hash in target_tree.items():
            content = self._get_blob_content(blob_hash)
            abs_path = self.root / fpath
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(content)

        # Remove files from current tree not in target
        for fpath in current_tree:
            if fpath not in target_tree:
                abs_path = self.root / fpath
                if abs_path.exists():
                    abs_path.unlink()

        # Update HEAD to point to branch
        self._write_head_raw(f"ref: refs/heads/{name}")

        # Clear index
        self._write_index({})

        print(f"Switched to branch '{name}'")
