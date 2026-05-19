#!/usr/bin/env python3
"""Core repository logic for the simplified VCS."""

import os
import sys
import json
import hashlib
import difflib
from datetime import datetime


class Repository:
    def __init__(self, path="."):
        self.work_dir = os.path.abspath(path)
        self.vcs_dir = os.path.join(self.work_dir, ".vcs")
        self.objects_dir = os.path.join(self.vcs_dir, "objects")
        self.refs_dir = os.path.join(self.vcs_dir, "refs", "heads")
        self.head_file = os.path.join(self.vcs_dir, "HEAD")
        self.index_file = os.path.join(self.vcs_dir, "index")
        self.commits_dir = os.path.join(self.vcs_dir, "commits")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _ensure_initialized(self):
        if not os.path.isdir(self.vcs_dir):
            print("Error: Not a vcs repository. Run 'vcs init' first.")
            sys.exit(1)

    def _resolve_hash(self, partial_hash):
        """Resolve a partial (or full) commit hash to the full hash."""
        if not partial_hash:
            return None
        # Full hash match
        commit_path = os.path.join(self.commits_dir, partial_hash + ".json")
        if os.path.isfile(commit_path):
            return partial_hash
        # Prefix search
        if os.path.isdir(self.commits_dir):
            for filename in os.listdir(self.commits_dir):
                if filename.startswith(partial_hash) and filename.endswith(".json"):
                    return filename[:-5]  # strip .json
        return None

    # ------------------------------------------------------------------
    # HEAD / branch helpers
    # ------------------------------------------------------------------
    def _get_current_branch(self):
        """Return branch name or None if detached HEAD."""
        try:
            with open(self.head_file) as f:
                head = f.read().strip()
        except (FileNotFoundError, IOError):
            return None
        if head.startswith("ref: refs/heads/"):
            return head[16:]
        return None

    def _get_branch_commit(self, branch_name):
        branch_file = os.path.join(self.refs_dir, branch_name)
        if not os.path.isfile(branch_file):
            return None
        with open(branch_file) as f:
            commit_hash = f.read().strip()
        return commit_hash if commit_hash else None

    def _set_branch(self, branch_name, commit_hash):
        branch_file = os.path.join(self.refs_dir, branch_name)
        os.makedirs(os.path.dirname(branch_file), exist_ok=True)
        with open(branch_file, 'w') as f:
            f.write(commit_hash)

    def _get_head_commit(self):
        """Return the commit hash currently pointed to by HEAD."""
        branch = self._get_current_branch()
        if branch:
            return self._get_branch_commit(branch)
        # Detached HEAD
        try:
            with open(self.head_file) as f:
                head = f.read().strip()
            if head and not head.startswith("ref:"):
                return head
        except (FileNotFoundError, IOError):
            pass
        return None

    # ------------------------------------------------------------------
    # Object store (content-addressable)
    # ------------------------------------------------------------------
    def _store_object(self, content: bytes) -> str:
        """Store content as a blob; return its SHA-1 hash."""
        blob_hash = hashlib.sha1(content).hexdigest()
        obj_path = os.path.join(self.objects_dir, blob_hash[:2], blob_hash[2:])
        if not os.path.exists(obj_path):
            os.makedirs(os.path.dirname(obj_path), exist_ok=True)
            with open(obj_path, 'wb') as f:
                f.write(content)
        return blob_hash

    def _read_object(self, blob_hash: str) -> bytes:
        obj_path = os.path.join(self.objects_dir, blob_hash[:2], blob_hash[2:])
        if os.path.isfile(obj_path):
            with open(obj_path, 'rb') as f:
                return f.read()
        return None

    # ------------------------------------------------------------------
    # Commit persistence
    # ------------------------------------------------------------------
    def _load_commit(self, commit_hash: str) -> dict | None:
        commit_path = os.path.join(self.commits_dir, commit_hash + ".json")
        if os.path.isfile(commit_path):
            with open(commit_path) as f:
                return json.load(f)
        return None

    def _save_commit(self, commit_data: dict):
        commit_hash = commit_data['hash']
        commit_path = os.path.join(self.commits_dir, commit_hash + ".json")
        os.makedirs(os.path.dirname(commit_path), exist_ok=True)
        with open(commit_path, 'w') as f:
            json.dump(commit_data, f, indent=2)

    # ------------------------------------------------------------------
    # Index (staging area)
    # ------------------------------------------------------------------
    def _load_index(self) -> dict:
        try:
            with open(self.index_file) as f:
                return json.load(f)
        except (FileNotFoundError, IOError, json.JSONDecodeError):
            return {}

    def _save_index(self, index: dict):
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, 'w') as f:
            json.dump(index, f, indent=2)

    # ------------------------------------------------------------------
    # Binary detection
    # ------------------------------------------------------------------
    def _is_binary(self, filepath: str) -> bool:
        """Return True if the file appears to be binary."""
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(4096)
            if b'\x00' in chunk:
                return True
            # Try decoding as UTF-8
            try:
                chunk.decode('utf-8')
                return False
            except UnicodeDecodeError:
                return True
        except (OSError, IOError):
            return False

    # ------------------------------------------------------------------
    # Utility: scan working directory  (skipping .vcs)
    # ------------------------------------------------------------------
    def _scan_working_files(self) -> dict:
        """Return {relpath: blob_hash} for every file in the work tree."""
        result = {}
        for root, dirs, files in os.walk(self.work_dir):
            # Skip the .vcs directory
            if '.vcs' in root.split(os.sep):
                continue
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, self.work_dir)
                try:
                    with open(full, 'rb') as f:
                        content = f.read()
                    result[rel] = hashlib.sha1(content).hexdigest()
                except (OSError, IOError):
                    pass
        return result

    # ------------------------------------------------------------------
    # COMMANDS
    # ------------------------------------------------------------------
    def init(self):
        if os.path.isdir(self.vcs_dir):
            print("Repository already initialized.")
            return
        os.makedirs(self.objects_dir, exist_ok=True)
        os.makedirs(self.refs_dir, exist_ok=True)
        os.makedirs(self.commits_dir, exist_ok=True)
        # HEAD -> main branch (branch file created on first commit)
        with open(self.head_file, 'w') as f:
            f.write("ref: refs/heads/main")
        # Empty index
        self._save_index({})
        # Create empty main branch file
        main_branch_path = os.path.join(self.refs_dir, "main")
        with open(main_branch_path, 'w') as f:
            f.write("")
        print(f"Initialized empty vcs repository in {self.vcs_dir}")

    def add(self, files: list[str]):
        self._ensure_initialized()
        index = self._load_index()

        for fp in files:
            full = os.path.join(self.work_dir, fp)
            if not os.path.isfile(full):
                print(f"Error: '{fp}' not found.")
                continue
            with open(full, 'rb') as f:
                content = f.read()
            blob_hash = self._store_object(content)
            index[fp] = blob_hash
            print(f"Staged '{fp}'")

        self._save_index(index)

    def commit(self, message: str, author: str = "vcs"):
        self._ensure_initialized()
        index = self._load_index()

        if not index:
            print("Nothing to commit (staging area is empty)")
            return

        # Build tree: start from parent's tree, override with staged files
        parent_hash = self._get_head_commit()
        tree = {}
        if parent_hash:
            parent_commit = self._load_commit(parent_hash)
            if parent_commit:
                tree = dict(parent_commit.get('tree', {}))

        for fp, blob_hash in index.items():
            tree[fp] = blob_hash

        timestamp = datetime.now().isoformat()

        # Generate commit hash from its content
        commit_content = json.dumps({
            'message': message,
            'timestamp': timestamp,
            'author': author,
            'parent': parent_hash,
            'tree': tree,
        }, sort_keys=True)
        commit_hash = hashlib.sha1(commit_content.encode()).hexdigest()

        commit_data = {
            'hash': commit_hash,
            'message': message,
            'timestamp': timestamp,
            'author': author,
            'parent': parent_hash,
            'tree': tree,
        }

        self._save_commit(commit_data)

        # Update current branch (or create it)
        branch = self._get_current_branch()
        if branch:
            self._set_branch(branch, commit_hash)

        # Clear staging area after commit
        self._save_index({})

        print(f"Committed: {commit_hash[:8]}")
        print(f"  Message: {message}")

    def status(self):
        self._ensure_initialized()
        head_commit = self._get_head_commit()
        index = self._load_index()
        branch = self._get_current_branch()

        if branch:
            print(f"On branch {branch}")
        else:
            print(f"HEAD detached at {head_commit[:8] if head_commit else 'unknown'}")

        if not head_commit:
            print("\nNo commits yet.")
            if index:
                print("\nChanges to be committed:")
                for f in sorted(index):
                    print(f"  new file: {f}")
            else:
                print("(use 'vcs add <file>' to stage files)")
            return

        commit_data = self._load_commit(head_commit)
        if not commit_data:
            print("Error: Current commit not found.")
            return

        tree = commit_data.get('tree', {})
        working = self._scan_working_files()

        new_files = []
        modified_files = []
        deleted_files = []

        # Files not staged: working vs HEAD, but skip files already in index
        for fp in sorted(working):
            if fp in index:
                continue  # already staged, don't show as unstaged
            if fp not in tree:
                new_files.append(fp)
            elif tree[fp] != working[fp]:
                modified_files.append(fp)

        for fp in sorted(tree):
            if fp not in working:
                deleted_files.append(fp)

        # Show staged changes
        if index:
            print("\nChanges to be committed:")
            for f in sorted(index):
                if f not in tree:
                    print(f"  new file: {f}")
                elif index[f] != tree.get(f):
                    print(f"  modified: {f}")
                else:
                    print(f"  unchanged: {f}")

        if not new_files and not modified_files and not deleted_files and not index:
            print("nothing to commit, working tree clean")
            return

        if new_files or modified_files or deleted_files:
            print("\nChanges not staged for commit:")
            for f in new_files:
                print(f"  new file: {f}")
            for f in modified_files:
                print(f"  modified: {f}")
            for f in deleted_files:
                print(f"  deleted: {f}")
            print("\n  (use 'vcs add <file>' to stage)")

    def log(self):
        self._ensure_initialized()
        head_commit = self._get_head_commit()

        if not head_commit:
            print("No commits yet.")
            return

        current = head_commit
        while current:
            commit = self._load_commit(current)
            if not commit:
                break
            print(f"commit {commit['hash']}")
            print(f"Author: {commit['author']}")
            print(f"Date:   {commit['timestamp']}")
            print(f"\n    {commit['message']}\n")
            current = commit.get('parent')

    def diff(self):
        self._ensure_initialized()
        head_commit = self._get_head_commit()

        if not head_commit:
            print("No commits to diff against.")
            return

        commit_data = self._load_commit(head_commit)
        if not commit_data:
            print("Error: Current commit not found.")
            return

        tree = commit_data.get('tree', {})
        working = self._scan_working_files()

        all_files = sorted(set(list(tree.keys()) + list(working.keys())))

        for fp in all_files:
            full = os.path.join(self.work_dir, fp)

            # Old content
            old_blob = self._read_object(tree[fp]) if fp in tree else None
            old_content = old_blob if old_blob else b""

            # Detect binary
            is_binary = False
            if fp in working and os.path.isfile(full):
                is_binary = self._is_binary(full)

            if is_binary:
                if fp not in tree:
                    print(f"Binary file {fp}: new file")
                elif fp not in working:
                    print(f"Binary file {fp}: deleted")
                elif tree[fp] != working[fp]:
                    print(f"Binary file {fp}: differs")
                continue

            # New content for text file
            new_content = b""
            if fp in working and os.path.isfile(full):
                with open(full, 'rb') as f:
                    new_content = f.read()

            old_lines = old_content.decode('utf-8', errors='replace').splitlines(keepends=True)
            new_lines = new_content.decode('utf-8', errors='replace').splitlines(keepends=True)

            if old_lines == new_lines:
                continue

            # Build fromfile/tofile strings
            if fp not in tree:
                fromfile = "/dev/null"
            else:
                fromfile = f"a/{fp}  (commit {head_commit[:8]})"
            if fp not in working:
                tofile = "/dev/null"
            else:
                tofile = f"b/{fp}"

            diff_lines = difflib.unified_diff(old_lines, new_lines,
                                              fromfile=fromfile,
                                              tofile=tofile)
            for line in diff_lines:
                print(line, end='')
            print()

    def checkout(self, commit_hash: str):
        self._ensure_initialized()

        actual = self._resolve_hash(commit_hash)
        if not actual:
            print(f"Error: Commit '{commit_hash}' not found.")
            return

        commit = self._load_commit(actual)
        if not commit:
            print(f"Error: Commit '{commit_hash}' not found.")
            return

        tree = commit.get('tree', {})

        # Remove tracked files that are NOT in the target commit
        # (First figure out what was tracked in the current commit)
        current_head = self._get_head_commit()
        if current_head:
            current_commit = self._load_commit(current_head)
            if current_commit:
                current_tree = current_commit.get('tree', {})
                for fp in current_tree:
                    if fp not in tree:
                        full = os.path.join(self.work_dir, fp)
                        if os.path.isfile(full):
                            os.remove(full)

        # Restore all files from the target commit
        for fp, blob_hash in tree.items():
            content = self._read_object(blob_hash)
            if content is not None:
                full = os.path.join(self.work_dir, fp)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'wb') as f:
                    f.write(content)

        # Detach HEAD
        with open(self.head_file, 'w') as f:
            f.write(actual)

        # Clear index
        self._save_index({})
        print(f"Checked out commit: {actual[:8]}")

    def branch(self, name: str | None = None):
        """List branches or create a new one."""
        self._ensure_initialized()

        if name is None:
            # List branches
            current = self._get_current_branch()
            if os.path.isdir(self.refs_dir):
                branches = sorted(os.listdir(self.refs_dir))
                if not branches:
                    print("(no branches)")
                for b in branches:
                    prefix = "* " if b == current else "  "
                    commit_hash = self._get_branch_commit(b)
                    short = commit_hash[:8] if commit_hash else "(no commits)"
                    print(f"{prefix}{b}  {short}")
            return

        # Create a new branch
        head_commit = self._get_head_commit()
        if not head_commit:
            print("Error: No commits yet. Create a commit first.")
            return

        branch_file = os.path.join(self.refs_dir, name)
        if os.path.isfile(branch_file):
            print(f"Error: Branch '{name}' already exists.")
            return

        with open(branch_file, 'w') as f:
            f.write(head_commit)
        print(f"Created branch '{name}' at {head_commit[:8]}")

    def switch(self, branch_name: str):
        self._ensure_initialized()

        branch_file = os.path.join(self.refs_dir, branch_name)
        if not os.path.isfile(branch_file):
            print(f"Error: Branch '{branch_name}' not found.")
            return

        with open(branch_file) as f:
            target_commit = f.read().strip()

        # If target branch has no commits, just switch HEAD
        if not target_commit:
            with open(self.head_file, 'w') as f:
                f.write(f"ref: refs/heads/{branch_name}")
            self._save_index({})
            print(f"Switched to branch '{branch_name}' (no commits yet)")
            return

        commit = self._load_commit(target_commit)
        if not commit:
            print(f"Error: Commit for branch '{branch_name}' not found.")
            return

        target_tree = commit.get('tree', {})

        # Remove tracked files that are NOT in the target branch
        current_head = self._get_head_commit()
        if current_head:
            current_commit = self._load_commit(current_head)
            if current_commit:
                current_tree = current_commit.get('tree', {})
                for fp in current_tree:
                    if fp not in target_tree:
                        full = os.path.join(self.work_dir, fp)
                        if os.path.isfile(full):
                            os.remove(full)

        # Restore files from the target commit
        for fp, blob_hash in target_tree.items():
            content = self._read_object(blob_hash)
            if content is not None:
                full = os.path.join(self.work_dir, fp)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'wb') as f:
                    f.write(content)

        # Update HEAD to point to the branch
        with open(self.head_file, 'w') as f:
            f.write(f"ref: refs/heads/{branch_name}")

        # Clear index
        self._save_index({})
        print(f"Switched to branch '{branch_name}'")
