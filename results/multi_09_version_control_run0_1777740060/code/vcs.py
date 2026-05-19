#!/usr/bin/env python3
"""
vcs — A simplified Git-like Version Control System.

Usage:
    python vcs.py init
    python vcs.py status
    python vcs.py add <file>...
    python vcs.py commit -m "message"
    python vcs.py log
    python vcs.py diff
    python vcs.py checkout <commit_hash>
    python vcs.py branch <name>
    python vcs.py switch <name>
"""

import os
import sys
import hashlib
import datetime
import argparse
import difflib


# ──────────────────────────────────────────────────────────────────────
# Utility helpers
# ──────────────────────────────────────────────────────────────────────

def _sha1(data: bytes) -> str:
    """Return hex SHA-1 hash of *data*."""
    return hashlib.sha1(data).hexdigest()


def _is_binary(data: bytes) -> bool:
    """Heuristic: data is binary if it contains a null byte or cannot be
    decoded as UTF-8."""
    if b'\x00' in data:
        return True
    try:
        data.decode('utf-8')
        return False
    except UnicodeDecodeError:
        return True


def _read_file_safe(path: str) -> bytes | None:
    """Read file contents; return None if the file cannot be read."""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except (OSError, PermissionError):
        return None


# ──────────────────────────────────────────────────────────────────────
# ObjectStore
# ──────────────────────────────────────────────────────────────────────

class ObjectStore:
    """Content‑addressable object storage inside `.vcs/objects/`."""

    def __init__(self, objects_dir: str):
        self._root = objects_dir

    # -- store helpers -------------------------------------------------

    def _write_object(self, sha: str, data: bytes) -> str:
        """Write *data* to the two‑level object directory and return *sha*."""
        subdir = os.path.join(self._root, sha[:2])
        os.makedirs(subdir, exist_ok=True)
        path = os.path.join(subdir, sha[2:])
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(data)
        return sha

    def _read_object(self, sha: str) -> bytes | None:
        """Read raw object bytes, or None if it does not exist."""
        path = os.path.join(self._root, sha[:2], sha[2:])
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            return f.read()

    # -- blobs ---------------------------------------------------------

    def store_blob(self, data: bytes) -> str:
        """Store raw file content and return its SHA-1 hash."""
        sha = _sha1(data)
        # Prepend type marker so we can distinguish object types later if needed
        blob_data = b'blob ' + data
        return self._write_object(sha, blob_data)

    def get_blob(self, sha: str) -> bytes | None:
        """Retrieve blob content (stripping the type marker)."""
        raw = self._read_object(sha)
        if raw is None:
            return None
        # strip "blob " prefix
        if raw.startswith(b'blob '):
            return raw[5:]
        return raw  # backwards compat

    def blob_hash_for(self, data: bytes) -> str:
        """Return the SHA-1 that *would* be used for *data* (without storing)."""
        return _sha1(b'blob ' + data)

    def tree_hash_for(self, file_dict: dict[str, str]) -> str:
        """Return the SHA-1 that *would* be used for *file_dict* (without storing)."""
        lines = []
        for path in sorted(file_dict.keys()):
            lines.append(f"{path}:{file_dict[path]}")
        content = '\n'.join(lines).encode('utf-8')
        tree_data = b'tree ' + content
        return _sha1(tree_data)

    # -- trees ---------------------------------------------------------

    def store_tree(self, file_dict: dict[str, str]) -> str:
        """*file_dict* maps file path → blob hash.

        Serialize as sorted lines `path:hash` and store.
        """
        lines = []
        for path in sorted(file_dict.keys()):
            lines.append(f"{path}:{file_dict[path]}")
        content = '\n'.join(lines).encode('utf-8')
        tree_data = b'tree ' + content
        sha = _sha1(tree_data)
        return self._write_object(sha, tree_data)

    def get_tree(self, sha: str) -> dict[str, str]:
        """Return `{path: blob_hash}` dict from a tree object."""
        raw = self._read_object(sha)
        if raw is None:
            return {}
        if raw.startswith(b'tree '):
            raw = raw[5:]
        text = raw.decode('utf-8', errors='replace').strip()
        if not text:
            return {}
        result = {}
        for line in text.split('\n'):
            if ':' in line:
                path, blob_hash = line.split(':', 1)
                result[path] = blob_hash
        return result

    # -- commits -------------------------------------------------------

    def store_commit(self, parent: str | None, tree_hash: str,
                     message: str, author: str,
                     timestamp: str | None = None) -> str:
        """Create and store a commit object.  Returns its hash."""
        if timestamp is None:
            timestamp = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        parent_str = parent if parent else ''
        content = (
            f"parent:{parent_str}\n"
            f"tree:{tree_hash}\n"
            f"author:{author}\n"
            f"timestamp:{timestamp}\n"
            f"message:{message}\n"
        ).encode('utf-8')
        commit_data = b'commit ' + content
        sha = _sha1(commit_data)
        return self._write_object(sha, commit_data)

    def get_commit(self, sha: str) -> dict[str, str] | None:
        """Return commit metadata dict or None."""
        raw = self._read_object(sha)
        if raw is None:
            return None
        if raw.startswith(b'commit '):
            raw = raw[7:]
        text = raw.decode('utf-8', errors='replace')
        info = {}
        for line in text.strip().split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                info[key] = val
        return info if 'tree' in info else None

    def object_exists(self, sha: str) -> bool:
        """Check whether an object with the given hash exists."""
        path = os.path.join(self._root, sha[:2], sha[2:])
        return os.path.exists(path)


# ──────────────────────────────────────────────────────────────────────
# Index (staging area)
# ──────────────────────────────────────────────────────────────────────

class Index:
    """Manages `.vcs/index` – a flat file of `<path> <blob_hash>` lines."""

    def __init__(self, path: str):
        self._path = path

    def read(self) -> dict[str, str]:
        """Return `{file_path: blob_hash}`."""
        if not os.path.exists(self._path):
            return {}
        result = {}
        with open(self._path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    result[parts[0]] = parts[1]
        return result

    def write(self, entries: dict[str, str]) -> None:
        """Write entries (sorted by path) to the index file."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            for path in sorted(entries.keys()):
                f.write(f"{path} {entries[path]}\n")

    def add(self, file_path: str, blob_hash: str) -> None:
        """Add or update a single entry."""
        entries = self.read()
        entries[file_path] = blob_hash
        self.write(entries)

    def clear(self) -> None:
        """Empty the index."""
        self.write({})

    def remove(self, file_path: str) -> None:
        """Remove a single path from the index."""
        entries = self.read()
        entries.pop(file_path, None)
        self.write(entries)


# ──────────────────────────────────────────────────────────────────────
# Repository
# ──────────────────────────────────────────────────────────────────────

class Repository:
    """High‑level operations on a vcs repository."""

    def __init__(self, root: str = '.'):
        self.root = os.path.abspath(root)
        self.vcs_dir = os.path.join(self.root, '.vcs')
        self.objects_dir = os.path.join(self.vcs_dir, 'objects')
        self.refs_heads_dir = os.path.join(self.vcs_dir, 'refs', 'heads')
        self.head_file = os.path.join(self.vcs_dir, 'HEAD')
        self.index_file = os.path.join(self.vcs_dir, 'index')

        self.objects = ObjectStore(self.objects_dir)
        self.index = Index(self.index_file)

    # -- helpers -------------------------------------------------------

    def _require_repo(self) -> None:
        """Die if not inside a repository."""
        if not os.path.isdir(self.vcs_dir):
            print("fatal: not a vcs repository (or any of the parent directories): .vcs",
                  file=sys.stderr)
            sys.exit(1)

    def _head_ref(self) -> str | None:
        """Read `.vcs/HEAD` and return the target reference.

        If detached HEAD (raw hash), return the hash.
        If symbolic (`ref: refs/heads/...`), return the path inside .vcs.
        """
        if not os.path.exists(self.head_file):
            return None
        with open(self.head_file, 'r') as f:
            content = f.read().strip()
        if content.startswith('ref: '):
            return content[5:]  # e.g. "refs/heads/master"
        return content  # detached – raw hash

    def _current_branch(self) -> str | None:
        """Return the current branch name, or None if detached."""
        ref = self._head_ref()
        if ref and ref.startswith('refs/heads/'):
            return ref[len('refs/heads/'):]
        return None

    def _resolve_head(self) -> str | None:
        """Return the SHA of the commit that HEAD points to, or None."""
        ref = self._head_ref()
        if ref is None:
            return None
        # symbolic?
        if ref.startswith('refs/'):
            path = os.path.join(self.vcs_dir, ref)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return f.read().strip()
            return None
        # detached (raw hash)
        return ref

    def _write_head(self, ref: str) -> None:
        """Write HEAD.  If *ref* starts with 'refs/', write symbolic;
        otherwise write raw hash (detached)."""
        if ref.startswith('refs/'):
            content = f"ref: {ref}"
        else:
            content = ref
        with open(self.head_file, 'w') as f:
            f.write(content + '\n')

    def _update_ref(self, ref_name: str, sha: str) -> None:
        """Update the branch reference file to point to *sha*."""
        path = os.path.join(self.vcs_dir, ref_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(sha + '\n')

    def _read_ref(self, ref_name: str) -> str | None:
        """Read the SHA stored in a reference file."""
        path = os.path.join(self.vcs_dir, ref_name)
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return f.read().strip()

    def _working_files(self) -> list[str]:
        """Return list of all regular files in working directory,
        excluding the `.vcs` directory."""
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Skip .vcs directory
            if '.vcs' in dirnames:
                dirnames.remove('.vcs')
            # Also skip other dot-directories that might interfere
            for name in list(dirnames):
                if name.startswith('.'):
                    # But only skip .vcs, keep others? Actually let's only skip .vcs
                    pass
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, self.root).replace('\\', '/')
                if os.path.isfile(full) and not rel.startswith('.vcs'):
                    files.append(rel)
        return files

    def _head_tree(self) -> dict[str, str]:
        """Return the tree `{path: blob_hash}` of the HEAD commit, or {}."""
        sha = self._resolve_head()
        if sha is None:
            return {}
        commit = self.objects.get_commit(sha)
        if commit is None:
            return {}
        return self.objects.get_tree(commit['tree'])

    # -- init ----------------------------------------------------------

    def init(self) -> None:
        """Initialise a new repository."""
        if os.path.exists(self.vcs_dir):
            print("A vcs repository already exists here.", file=sys.stderr)
            sys.exit(1)
        os.makedirs(self.objects_dir, exist_ok=True)
        os.makedirs(self.refs_heads_dir, exist_ok=True)
        # Write symbolic HEAD → master
        self._write_head('refs/heads/master')
        # Empty index
        self.index.clear()
        print(f"Initialised empty vcs repository in {self.vcs_dir}")

    # -- status --------------------------------------------------------

    def status(self) -> None:
        """Show working‑tree status."""
        self._require_repo()

        head_tree = self._head_tree()          # {path: blob_hash} – tracked
        index_entries = self.index.read()       # {path: blob_hash} – staged
        working_files = set(self._working_files())

        all_paths = set(head_tree.keys()) | set(index_entries.keys()) | working_files

        staged_new = []
        staged_modified = []
        modified_not_staged = []
        deleted = []
        untracked = []

        for path in sorted(all_paths):
            in_head = path in head_tree
            in_index = path in index_entries
            in_work = path in working_files

            if in_index:
                # Staged – distinguish new vs modified vs identical relative to HEAD
                if not in_head:
                    staged_new.append(path)
                elif index_entries[path] != head_tree[path]:
                    staged_modified.append(path)
                # else: identical – skip, nothing to report
                continue

            if in_head and not in_work:
                deleted.append(path)
                continue

            if in_head and in_work:
                # Check if modified relative to HEAD (unstaged modification)
                work_data = _read_file_safe(os.path.join(self.root, path))
                if work_data is not None:
                    work_hash = self.objects.blob_hash_for(work_data)
                    if work_hash != head_tree[path]:
                        modified_not_staged.append(path)
                continue

            if not in_head and in_work and not in_index:
                untracked.append(path)

        # Print results
        branch = self._current_branch()
        if branch:
            print(f"On branch {branch}")
        else:
            sha = self._resolve_head()
            if sha:
                print(f"HEAD detached at {sha[:7]}")
            else:
                print("No commits yet")

        if not (staged_new or staged_modified or modified_not_staged or deleted or untracked):
            print("nothing to commit, working tree clean")
            return

        if staged_new or staged_modified:
            print("\nChanges to be committed:")
            for p in staged_new:
                print(f"  new file:   {p}")
            for p in staged_modified:
                print(f"  modified:   {p}")

        if modified_not_staged:
            print("\nChanges not staged for commit:")
            for p in modified_not_staged:
                print(f"  modified:   {p}")

        if deleted:
            print("\nDeleted:")
            for p in deleted:
                print(f"  deleted:    {p}")

        if untracked:
            print("\nUntracked files:")
            for p in untracked:
                print(f"  {p}")

    # -- add -----------------------------------------------------------

    def add(self, paths: list[str]) -> None:
        """Stage files."""
        self._require_repo()

        for raw_path in paths:
            # Normalize path
            p = raw_path.replace('\\', '/')
            full = os.path.join(self.root, p)
            if not os.path.isfile(full):
                print(f"error: '{p}' does not exist", file=sys.stderr)
                continue
            data = _read_file_safe(full)
            if data is None:
                print(f"error: cannot read '{p}'", file=sys.stderr)
                continue
            blob_hash = self.objects.store_blob(data)
            self.index.add(p, blob_hash)
            print(f"staged: {p}")

    # -- commit --------------------------------------------------------

    def commit(self, message: str) -> None:
        """Create a new commit from staged files."""
        self._require_repo()

        if not message:
            print("error: commit message required (-m)", file=sys.stderr)
            sys.exit(1)

        index_entries = self.index.read()
        if not index_entries:
            print("nothing to commit (use 'add' to stage files)", file=sys.stderr)
            sys.exit(1)

        author = os.environ.get('VCS_AUTHOR', 'Unknown')
        parent_sha = self._resolve_head()

        # Build new tree
        # Start from parent tree
        if parent_sha:
            parent_commit = self.objects.get_commit(parent_sha)
            parent_tree = self.objects.get_tree(parent_commit['tree']) if parent_commit else {}
        else:
            parent_tree = {}

        new_tree = {}

        # For each tracked file in parent:
        for path, old_blob_hash in parent_tree.items():
            if path in index_entries:
                # Use staged version
                new_tree[path] = index_entries[path]
            else:
                # Check working-directory state
                full = os.path.join(self.root, path)
                if os.path.isfile(full):
                    data = _read_file_safe(full)
                    if data is not None:
                        work_hash = self.objects.blob_hash_for(data)
                        if work_hash == old_blob_hash:
                            # Unchanged – keep parent's blob
                            new_tree[path] = old_blob_hash
                        else:
                            # Modified but not staged – keep parent's blob (don't include changes)
                            new_tree[path] = old_blob_hash
                    else:
                        new_tree[path] = old_blob_hash
                else:
                    # File deleted – omit from new tree
                    pass

        # Add staged files that are not yet in new_tree
        for path, blob_hash in index_entries.items():
            new_tree[path] = blob_hash

        if not new_tree:
            print("error: resulting tree is empty", file=sys.stderr)
            sys.exit(1)

        # Compute tree hash without storing — compare against parent to
        # prevent empty commits.
        new_tree_hash = self.objects.tree_hash_for(new_tree)

        if parent_sha and parent_commit:
            parent_tree_hash = parent_commit.get('tree', '')
            if new_tree_hash == parent_tree_hash:
                print("nothing to commit, working tree clean", file=sys.stderr)
                return

        tree_hash = self.objects.store_tree(new_tree)
        commit_hash = self.objects.store_commit(
            parent=parent_sha,
            tree_hash=tree_hash,
            message=message,
            author=author,
        )

        # Update current branch reference
        ref = self._head_ref()
        if ref and ref.startswith('refs/'):
            self._update_ref(ref, commit_hash)
        else:
            # Detached HEAD – store directly
            self._write_head(commit_hash)

        self.index.clear()

        print(f"[{commit_hash[:7]}] {message}")

    # -- log -----------------------------------------------------------

    def log(self) -> None:
        """Print commit history."""
        self._require_repo()

        sha = self._resolve_head()
        if sha is None:
            print("No commits yet.", file=sys.stderr)
            return

        while sha:
            commit = self.objects.get_commit(sha)
            if commit is None:
                break
            print(f"commit {sha}")
            print(f"Author: {commit.get('author', 'Unknown')}")
            print(f"Date:   {commit.get('timestamp', '')}")
            print(f"\n    {commit.get('message', '')}\n")
            parent = commit.get('parent', '')
            sha = parent if parent else None

    # -- diff ----------------------------------------------------------

    def diff(self) -> None:
        """Show diff between working directory and HEAD commit."""
        self._require_repo()

        sha = self._resolve_head()
        if sha is None:
            print("No commits to diff against.", file=sys.stderr)
            return

        commit = self.objects.get_commit(sha)
        if commit is None:
            print("Cannot read HEAD commit.", file=sys.stderr)
            return

        head_tree = self.objects.get_tree(commit['tree'])
        working_files = set(self._working_files())

        all_paths = set(head_tree.keys()) | working_files

        for path in sorted(all_paths):
            in_head = path in head_tree
            in_work = path in working_files

            if in_head and not in_work:
                # File deleted
                print(f"--- a/{path}")
                print(f"+++ /dev/null")
                old_data = self.objects.get_blob(head_tree[path])
                if old_data is not None:
                    old_text = old_data.decode('utf-8', errors='replace')
                    for line in old_text.splitlines(keepends=True):
                        print(f"-{line.rstrip()}")
                print()
                continue

            if not in_head and in_work:
                # New file
                print(f"--- /dev/null")
                print(f"+++ b/{path}")
                new_data = _read_file_safe(os.path.join(self.root, path))
                if new_data is not None:
                    new_text = new_data.decode('utf-8', errors='replace')
                    for line in new_text.splitlines(keepends=True):
                        print(f"+{line.rstrip()}")
                print()
                continue

            # Both exist – compare
            old_data = self.objects.get_blob(head_tree[path])
            new_data = _read_file_safe(os.path.join(self.root, path))

            if old_data is None or new_data is None:
                continue

            if old_data == new_data:
                continue

            if _is_binary(old_data) or _is_binary(new_data):
                print(f"Binary file {path} differs")
                continue

            old_text = old_data.decode('utf-8', errors='replace')
            new_text = new_data.decode('utf-8', errors='replace')

            diff_lines = list(difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f'a/{path}',
                tofile=f'b/{path}',
            ))

            if diff_lines:
                for line in diff_lines:
                    print(line.rstrip())
                print()

    # -- checkout ------------------------------------------------------

    def checkout(self, commit_hash: str) -> None:
        """Restore working directory to the state of *commit_hash*.

        Operates in detached HEAD mode unless the hash matches a branch tip.
        """
        self._require_repo()

        # Resolve partial hash — look for matching object
        full_hash = self._resolve_hash(commit_hash)
        if full_hash is None:
            print(f"error: commit '{commit_hash}' not found", file=sys.stderr)
            sys.exit(1)

        commit = self.objects.get_commit(full_hash)
        if commit is None:
            print(f"error: '{commit_hash}' is not a commit", file=sys.stderr)
            sys.exit(1)

        target_tree = self.objects.get_tree(commit['tree'])
        current_tree = self._head_tree()

        # Write target tree files
        for path, blob_hash in target_tree.items():
            blob = self.objects.get_blob(blob_hash)
            if blob is None:
                print(f"warning: blob {blob_hash} missing for {path}", file=sys.stderr)
                continue
            full_path = os.path.join(self.root, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(blob)

        # Remove files that were tracked but are not in target
        for path in current_tree:
            if path not in target_tree:
                full_path = os.path.join(self.root, path)
                if os.path.isfile(full_path):
                    os.remove(full_path)

        # Check if this hash corresponds to a branch tip
        branch_name = self._branch_for_hash(full_hash)
        if branch_name:
            self._write_head(f'refs/heads/{branch_name}')
            print(f"Switched to branch '{branch_name}'")
        else:
            self._write_head(full_hash)
            print(f"HEAD is now at {full_hash[:7]}")

    def _resolve_hash(self, short_hash: str) -> str | None:
        """Resolve a possibly‑short hash to a full SHA‑1 by scanning objects."""
        if len(short_hash) == 40 and self.objects.object_exists(short_hash):
            return short_hash

        # Scan objects directory for matching prefix
        prefix = short_hash[:2] if len(short_hash) >= 2 else short_hash
        subdir = os.path.join(self.objects_dir, prefix)
        if not os.path.isdir(subdir):
            return None

        for fname in os.listdir(subdir):
            full = prefix + fname
            if full.startswith(short_hash):
                return full
        return None

    def _branch_for_hash(self, commit_hash: str) -> str | None:
        """Return the branch name whose tip is *commit_hash*, or None."""
        if not os.path.isdir(self.refs_heads_dir):
            return None
        for fname in os.listdir(self.refs_heads_dir):
            ref_path = os.path.join(self.refs_heads_dir, fname)
            with open(ref_path, 'r') as f:
                if f.read().strip() == commit_hash:
                    return fname
        return None

    # -- branch --------------------------------------------------------

    def branch(self, name: str) -> None:
        """Create a new branch at HEAD."""
        self._require_repo()

        sha = self._resolve_head()
        if sha is None:
            print("error: no commits yet — cannot create branch", file=sys.stderr)
            sys.exit(1)

        # Validate branch name
        if not name or '/' in name or '\\' in name or ' ' in name:
            print(f"error: invalid branch name '{name}'", file=sys.stderr)
            sys.exit(1)

        branch_path = os.path.join(self.refs_heads_dir, name)
        if os.path.exists(branch_path):
            print(f"error: branch '{name}' already exists", file=sys.stderr)
            sys.exit(1)

        self._update_ref(f'refs/heads/{name}', sha)
        print(f"Created branch '{name}' at {sha[:7]}")

    # -- switch --------------------------------------------------------

    def switch(self, name: str) -> None:
        """Switch to an existing branch."""
        self._require_repo()

        ref_path = os.path.join(self.refs_heads_dir, name)
        if not os.path.exists(ref_path):
            print(f"error: branch '{name}' does not exist", file=sys.stderr)
            sys.exit(1)

        with open(ref_path, 'r') as f:
            target_hash = f.read().strip()

        commit = self.objects.get_commit(target_hash)
        if commit is None:
            print(f"error: branch '{name}' points to invalid commit", file=sys.stderr)
            sys.exit(1)

        target_tree = self.objects.get_tree(commit['tree'])
        current_tree = self._head_tree()

        # Write target tree files
        for path, blob_hash in target_tree.items():
            blob = self.objects.get_blob(blob_hash)
            if blob is None:
                print(f"warning: blob {blob_hash} missing for {path}", file=sys.stderr)
                continue
            full_path = os.path.join(self.root, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(blob)

        # Remove files that were tracked but are not in target
        for path in current_tree:
            if path not in target_tree:
                full_path = os.path.join(self.root, path)
                if os.path.isfile(full_path):
                    os.remove(full_path)

        # Update HEAD
        self._write_head(f'refs/heads/{name}')
        print(f"Switched to branch '{name}'")


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='vcs',
        description='Simplified Git-like Version Control System',
    )
    sub = parser.add_subparsers(dest='command', help='subcommands')

    # init
    sub.add_parser('init', help='Initialize a new repository')

    # status
    sub.add_parser('status', help='Show working-tree status')

    # add
    p_add = sub.add_parser('add', help='Stage files for commit')
    p_add.add_argument('files', nargs='+', help='Files to stage')

    # commit
    p_commit = sub.add_parser('commit', help='Commit staged changes')
    p_commit.add_argument('-m', '--message', required=True, help='Commit message')

    # log
    sub.add_parser('log', help='Show commit history')

    # diff
    sub.add_parser('diff', help='Show diff between working directory and HEAD')

    # checkout
    p_checkout = sub.add_parser('checkout', help='Restore working directory to a commit')
    p_checkout.add_argument('commit', help='Commit hash (or prefix)')

    # branch
    p_branch = sub.add_parser('branch', help='Create a new branch')
    p_branch.add_argument('name', help='Branch name')

    # switch
    p_switch = sub.add_parser('switch', help='Switch to a branch')
    p_switch.add_argument('name', help='Branch name')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    repo = Repository()

    if args.command == 'init':
        repo.init()
    elif args.command == 'status':
        repo.status()
    elif args.command == 'add':
        repo.add(args.files)
    elif args.command == 'commit':
        repo.commit(args.message)
    elif args.command == 'log':
        repo.log()
    elif args.command == 'diff':
        repo.diff()
    elif args.command == 'checkout':
        repo.checkout(args.commit)
    elif args.command == 'branch':
        repo.branch(args.name)
    elif args.command == 'switch':
        repo.switch(args.name)


if __name__ == '__main__':
    main()
