#!/usr/bin/env python3
"""
vcs - A simplified Git-like version control system.

Usage:
    python vcs.py init
    python vcs.py status
    python vcs.py add <file...>
    python vcs.py commit -m "<message>"
    python vcs.py log
    python vcs.py diff [file]
    python vcs.py checkout <commit-hash>
    python vcs.py branch <name>
    python vcs.py switch <name>
"""

import sys
import os
import json
import hashlib
import time
import getpass
import difflib
from pathlib import Path

VCS_DIR = ".vcs"
OBJECTS_DIR = os.path.join(VCS_DIR, "objects")
REFS_DIR = os.path.join(VCS_DIR, "refs", "heads")
HEAD_FILE = os.path.join(VCS_DIR, "HEAD")
INDEX_FILE = os.path.join(VCS_DIR, "index")


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def find_repo_root():
    """Walk up from cwd to find the .vcs directory. Returns Path or None."""
    path = Path.cwd()
    while True:
        if (path / VCS_DIR).is_dir():
            return path
        if path.parent == path:
            return None
        path = path.parent


def require_repo():
    """Return repo root or exit with error."""
    root = find_repo_root()
    if root is None:
        print("error: not a vcs repository (or any parent directory)")
        sys.exit(1)
    return root


def hash_content(data: bytes) -> str:
    """Return SHA-256 hex digest of data."""
    return hashlib.sha256(data).hexdigest()


def object_path(hash_str: str) -> str:
    """Return the filesystem path to an object given its hash."""
    return os.path.join(OBJECTS_DIR, hash_str[:2], hash_str[2:])


def store_object(data: bytes) -> str:
    """Store data in .vcs/objects and return its hash. Skips if exists."""
    h = hash_content(data)
    p = object_path(h)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(data)
    return h


def read_object(hash_str: str, repo_root: Path) -> bytes:
    """Read an object from storage by hash."""
    p = repo_root / object_path(hash_str)
    if not p.exists():
        print(f"error: object {hash_str[:8]} not found in repository")
        sys.exit(1)
    with open(p, "rb") as f:
        return f.read()


def read_index(repo_root: Path) -> dict:
    """Read the staging index; returns dict of filename -> content_hash."""
    idx_path = repo_root / INDEX_FILE
    if idx_path.exists():
        with open(idx_path, "r") as f:
            return json.load(f)
    return {}


def write_index(repo_root: Path, index: dict):
    """Write the staging index."""
    idx_path = repo_root / INDEX_FILE
    with open(idx_path, "w") as f:
        json.dump(index, f, indent=2, sort_keys=True)


def read_head_ref(repo_root: Path) -> str | None:
    """Return the commit hash pointed to by HEAD (via branch or detached)."""
    head_path = repo_root / HEAD_FILE
    if not head_path.exists():
        return None
    with open(head_path, "r") as f:
        content = f.read().strip()
    if content.startswith("ref: "):
        ref_path = content[5:]  # e.g. "refs/heads/main"
        full_ref = repo_root / VCS_DIR / ref_path
        if full_ref.exists():
            with open(full_ref, "r") as f:
                return f.read().strip()
        return None
    else:
        # Detached HEAD (raw commit hash)
        return content if content else None


def get_current_branch(repo_root: Path) -> str | None:
    """Return the current branch name, or None if detached."""
    head_path = repo_root / HEAD_FILE
    if not head_path.exists():
        return None
    with open(head_path, "r") as f:
        content = f.read().strip()
    if content.startswith("ref: refs/heads/"):
        return content[len("ref: refs/heads/"):]
    return None


def write_head_ref(repo_root: Path, ref: str):
    """Write HEAD pointing to a branch reference."""
    head_path = repo_root / HEAD_FILE
    with open(head_path, "w") as f:
        f.write(f"ref: {ref}\n")


def write_head_detached(repo_root: Path, commit_hash: str):
    """Write HEAD as detached (raw commit hash)."""
    head_path = repo_root / HEAD_FILE
    with open(head_path, "w") as f:
        f.write(commit_hash + "\n")


def update_branch_ref(repo_root: Path, branch: str, commit_hash: str):
    """Update a branch reference to point to a commit."""
    ref_path = repo_root / REFS_DIR / branch
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, "w") as f:
        f.write(commit_hash + "\n")


def read_branch_ref(repo_root: Path, branch: str) -> str | None:
    """Read a branch reference; returns commit hash or None."""
    ref_path = repo_root / REFS_DIR / branch
    if ref_path.exists():
        with open(ref_path, "r") as f:
            return f.read().strip()
    return None


def read_commit(hash_str: str, repo_root: Path) -> dict:
    """Read and parse a commit object."""
    data = read_object(hash_str, repo_root)
    commit = json.loads(data.decode("utf-8"))
    commit["hash"] = hash_str
    return commit


def get_commit_tree(commit_hash: str, repo_root: Path) -> dict:
    """Return the tree (filename -> content_hash) for a commit."""
    commit = read_commit(commit_hash, repo_root)
    return commit.get("tree", {})


def build_commit_object(parent: str | None, message: str,
                        tree: dict, repo_root: Path) -> str:
    """Build a commit object, store it, and return its hash."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %z")
    author = getpass.getuser()

    commit_data = {
        "parent": parent,
        "message": message,
        "timestamp": timestamp,
        "author": author,
        "tree": tree,
    }
    raw = json.dumps(commit_data, indent=2, sort_keys=True)
    h = hash_content(raw.encode("utf-8"))
    p = repo_root / object_path(h)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not p.exists():
        with open(p, "wb") as f:
            f.write(raw.encode("utf-8"))
    return h


def is_binary(filepath: Path) -> bool:
    """Heuristic: try to read as text; if null bytes or decode error -> binary."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
        if b"\x00" in chunk:
            return True
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def get_working_files(repo_root: Path) -> dict:
    """
    Walk the working directory and return {relative_path: content_hash}
    for all files (excluding .vcs directory).
    """
    result = {}
    vcs_path = repo_root / VCS_DIR
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip .vcs directory
        if VCS_DIR in dirnames:
            dirnames.remove(VCS_DIR)
        for fname in filenames:
            full_path = Path(dirpath) / fname
            try:
                full_path.relative_to(vcs_path)
                continue
            except ValueError:
                pass
            rel_path = str(full_path.relative_to(repo_root))
            try:
                with open(full_path, "rb") as f:
                    data = f.read()
                result[rel_path] = hash_content(data)
            except (OSError, PermissionError):
                continue
    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init():
    """Initialize a new vcs repository in the current directory."""
    repo_root = Path.cwd()
    vcs_path = repo_root / VCS_DIR

    if vcs_path.exists():
        print("Reinitialized existing vcs repository")
        return

    os.makedirs(vcs_path / "objects", exist_ok=True)
    os.makedirs(vcs_path / "refs" / "heads", exist_ok=True)
    write_head_ref(repo_root, "refs/heads/main")
    write_index(repo_root, {})

    print(f"Initialized empty vcs repository in {vcs_path}")


def cmd_status():
    """Show working tree status."""
    repo_root = require_repo()

    head_commit = read_head_ref(repo_root)
    index = read_index(repo_root)
    working = get_working_files(repo_root)

    committed_tree = {}
    if head_commit:
        committed_tree = get_commit_tree(head_commit, repo_root)

    committed_files = set(committed_tree.keys())
    indexed_files = set(index.keys())
    working_files = set(working.keys())

    # Staged: in index, different from committed
    staged_new = []
    staged_modified = []
    for f in indexed_files:
        if f not in committed_files:
            staged_new.append(f)
        elif index[f] != committed_tree.get(f, ""):
            staged_modified.append(f)

    # Not staged: working differs from committed (and not in index)
    not_staged_modified = []
    not_staged_deleted = []

    for f in committed_files:
        if f not in working_files:
            not_staged_deleted.append(f)
        elif f not in indexed_files:
            if working[f] != committed_tree[f]:
                not_staged_modified.append(f)

    for f in indexed_files:
        if f in working_files and working[f] != index[f]:
            if f not in not_staged_modified:
                not_staged_modified.append(f)
        elif f not in working_files:
            if f not in not_staged_deleted:
                not_staged_deleted.append(f)

    # Untracked
    untracked = []
    for f in working_files:
        if f not in committed_files and f not in indexed_files:
            untracked.append(f)

    branch = get_current_branch(repo_root) or "HEAD (detached)"
    print(f"On branch {branch}")

    if not head_commit:
        print("\nNo commits yet\n")

    if staged_new or staged_modified:
        print("Changes to be committed:")
        print('  (use "vcs add <file>..." to stage)')
        for f in sorted(staged_new):
            print(f"        new file:   {f}")
        for f in sorted(staged_modified):
            print(f"        modified:   {f}")
        print()

    if not_staged_modified or not_staged_deleted:
        print("Changes not staged for commit:")
        for f in sorted(not_staged_modified):
            print(f"        modified:   {f}")
        for f in sorted(not_staged_deleted):
            print(f"        deleted:    {f}")
        print()

    if untracked:
        print("Untracked files:")
        for f in sorted(untracked):
            print(f"        {f}")
        print()

    if not (staged_new or staged_modified or not_staged_modified or
            not_staged_deleted or untracked):
        if head_commit:
            print("nothing to commit, working tree clean")


def cmd_add(files: list[str]):
    """Stage files for commit."""
    repo_root = require_repo()
    index = read_index(repo_root)

    for filepath_str in files:
        filepath = repo_root / filepath_str
        if not filepath.exists():
            print(f"error: pathspec '{filepath_str}' did not match any files")
            continue
        if filepath.is_dir():
            print(f"error: '{filepath_str}' is a directory; skipping")
            continue
        try:
            with open(filepath, "rb") as f:
                data = f.read()
        except (OSError, PermissionError) as e:
            print(f"error: cannot read '{filepath_str}': {e}")
            continue

        # Store in objects
        h = hash_content(data)
        p = repo_root / object_path(h)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not p.exists():
            with open(p, "wb") as f:
                f.write(data)

        rel_path = str(filepath.relative_to(repo_root))
        index[rel_path] = h
        print(f"staged: {rel_path}")

    write_index(repo_root, index)


def cmd_commit(message: str):
    """Create a commit with staged files."""
    repo_root = require_repo()
    index = read_index(repo_root)

    if not index:
        print("nothing to commit (no files staged)")
        sys.exit(1)

    parent_hash = read_head_ref(repo_root)
    commit_hash = build_commit_object(parent_hash, message, dict(index), repo_root)

    # Update branch reference or HEAD
    head_path = repo_root / HEAD_FILE
    with open(head_path, "r") as f:
        head_content = f.read().strip()

    if head_content.startswith("ref: "):
        ref = head_content[5:]
        update_branch_ref(repo_root, ref.split("/")[-1], commit_hash)
    else:
        write_head_detached(repo_root, commit_hash)

    # Clear index after commit
    write_index(repo_root, {})

    print(f"[{commit_hash[:8]}] {message}")


def cmd_log():
    """Display commit history."""
    repo_root = require_repo()

    head_commit = read_head_ref(repo_root)
    if not head_commit:
        print("No commits yet.")
        return

    current = head_commit
    while current:
        commit = read_commit(current, repo_root)
        print(f"commit {commit['hash']}")
        print(f"Author: {commit['author']}")
        print(f"Date:   {commit['timestamp']}")
        print(f"\n    {commit['message']}\n")
        current = commit.get("parent")


def cmd_diff(target: str | None = None):
    """Show diff between working directory and last commit."""
    repo_root = require_repo()

    head_commit = read_head_ref(repo_root)
    if not head_commit:
        print("No commits to diff against.")
        return

    committed_tree = get_commit_tree(head_commit, repo_root)
    working = get_working_files(repo_root)

    if target:
        files_to_diff = [target]
    else:
        files_to_diff = sorted(set(list(committed_tree.keys()) + list(working.keys())))

    for rel_path in files_to_diff:
        if target is None:
            # Skip unchanged files
            if rel_path in committed_tree and rel_path in working:
                if committed_tree[rel_path] == working[rel_path]:
                    continue

        old_hash = committed_tree.get(rel_path)
        new_hash = working.get(rel_path)

        old_content = None
        new_content = None
        old_is_binary = False
        new_is_binary = False

        if old_hash:
            old_data = read_object(old_hash, repo_root)
            if b"\x00" in old_data:
                old_is_binary = True
            else:
                try:
                    old_content = old_data.decode("utf-8").splitlines(keepends=True)
                except UnicodeDecodeError:
                    old_is_binary = True

        if new_hash:
            filepath = repo_root / rel_path
            if is_binary(filepath):
                new_is_binary = True
            else:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        new_content = f.readlines()
                except (UnicodeDecodeError, OSError):
                    new_is_binary = True

        if old_is_binary or new_is_binary:
            if old_hash is None:
                print(f"diff --git a/{rel_path} b/{rel_path}")
                print(f"new file: {rel_path}")
                print("Binary file (diff skipped)")
                print()
            elif new_hash is None:
                print(f"diff --git a/{rel_path} b/{rel_path}")
                print(f"deleted file: {rel_path}")
                print("Binary file (diff skipped)")
                print()
            else:
                print(f"diff --git a/{rel_path} b/{rel_path}")
                print("Binary files differ (diff skipped)")
                print()
            continue

        a_label = f"a/{rel_path}"
        b_label = f"b/{rel_path}"

        if old_hash is None:
            old_content = []
            a_label = "/dev/null"
        if new_hash is None:
            new_content = []
            b_label = "/dev/null"

        diff_lines = list(difflib.unified_diff(
            old_content, new_content,
            fromfile=a_label, tofile=b_label,
            lineterm=""
        ))

        if diff_lines:
            for line in diff_lines:
                print(line)
            print()


def cmd_checkout(commit_hash: str):
    """Restore all files to the state of a specific commit."""
    repo_root = require_repo()

    try:
        commit = read_commit(commit_hash, repo_root)
    except SystemExit:
        print(f"error: commit '{commit_hash}' not found")
        sys.exit(1)

    tree = commit["tree"]

    # Remove files that exist in working but not in this commit
    working = get_working_files(repo_root)
    for rel_path in working:
        if rel_path not in tree:
            filepath = repo_root / rel_path
            try:
                os.remove(filepath)
            except OSError:
                pass

    # Restore files from commit
    for rel_path, content_hash in tree.items():
        filepath = repo_root / rel_path
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = read_object(content_hash, repo_root)
        with open(filepath, "wb") as f:
            f.write(data)

    write_head_detached(repo_root, commit_hash)
    write_index(repo_root, {})

    print(f"Checked out commit {commit_hash[:8]}")
    print(f"HEAD is now at {commit_hash[:8]} {commit['message']}")


def cmd_branch(name: str):
    """Create a new branch at the current commit."""
    repo_root = require_repo()

    existing = read_branch_ref(repo_root, name)
    if existing is not None:
        print(f"error: branch '{name}' already exists")
        sys.exit(1)

    head_commit = read_head_ref(repo_root)
    if not head_commit:
        print("error: no commits yet; cannot create branch")
        sys.exit(1)

    update_branch_ref(repo_root, name, head_commit)
    print(f"Created branch '{name}' at {head_commit[:8]}")


def cmd_switch(name: str):
    """Switch to a different branch."""
    repo_root = require_repo()

    commit_hash = read_branch_ref(repo_root, name)
    if commit_hash is None:
        print(f"error: branch '{name}' does not exist")
        sys.exit(1)

    write_head_ref(repo_root, f"refs/heads/{name}")

    commit = read_commit(commit_hash, repo_root)
    tree = commit["tree"]

    working = get_working_files(repo_root)

    # Remove files not in target branch
    for rel_path in working:
        if rel_path not in tree:
            filepath = repo_root / rel_path
            try:
                os.remove(filepath)
            except OSError:
                pass

    # Restore files
    for rel_path, content_hash in tree.items():
        filepath = repo_root / rel_path
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = read_object(content_hash, repo_root)
        with open(filepath, "wb") as f:
            f.write(data)

    write_index(repo_root, {})

    print(f"Switched to branch '{name}'")


# ---------------------------------------------------------------------------
# Main CLI dispatch
# ---------------------------------------------------------------------------

def print_usage():
    print("usage: vcs <command> [<args>]")
    print()
    print("Commands:")
    print("  init                  Initialize a new repository")
    print("  status                Show working tree status")
    print("  add <file...>         Stage files for commit")
    print("  commit -m <msg>       Commit staged changes")
    print("  log                   Show commit history")
    print("  diff [file]           Show diff between working dir and last commit")
    print("  checkout <hash>       Restore files to a specific commit")
    print("  branch <name>         Create a new branch")
    print("  switch <name>         Switch to a branch")


def main():
    args = sys.argv[1:]

    if not args:
        print_usage()
        sys.exit(0)

    command = args[0]

    if command == "init":
        cmd_init()
    elif command == "status":
        cmd_status()
    elif command == "add":
        if len(args) < 2:
            print("usage: vcs add <file...>")
            sys.exit(1)
        cmd_add(args[1:])
    elif command == "commit":
        if len(args) < 3 or args[1] != "-m":
            print("usage: vcs commit -m <message>")
            sys.exit(1)
        cmd_commit(args[2])
    elif command == "log":
        cmd_log()
    elif command == "diff":
        target = args[1] if len(args) > 1 else None
        cmd_diff(target)
    elif command == "checkout":
        if len(args) < 2:
            print("usage: vcs checkout <commit-hash>")
            sys.exit(1)
        cmd_checkout(args[1])
    elif command == "branch":
        if len(args) < 2:
            print("usage: vcs branch <name>")
            sys.exit(1)
        cmd_branch(args[1])
    elif command == "switch":
        if len(args) < 2:
            print("usage: vcs switch <name>")
            sys.exit(1)
        cmd_switch(args[1])
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
