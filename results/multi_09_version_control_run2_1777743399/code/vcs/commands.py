"""Implementation of each VCS subcommand."""

import os
import sys
from typing import Dict, List, Optional, Set

from repository import (
    init_repository,
    get_repo_root,
    resolve_head,
    read_head,
    write_head_ref,
    write_head_detached,
    is_head_detached,
    get_head_ref_name,
    read_ref,
    write_ref,
    create_branch,
    branch_exists,
    read_index,
    write_index,
    clear_index,
    store_blob,
    load_blob,
    store_commit,
    load_commit,
    object_exists,
    get_current_commit,
    get_author,
    get_timestamp,
)
from utils import (
    compute_blob_hash,
    is_binary,
    generate_unified_diff,
    short_hash,
)


def cmd_init() -> None:
    """Initialize a new VCS repository in the current directory."""
    try:
        root = init_repository()
        print(f"Initialized empty vcs repository in {os.path.join(root, '.vcs')}")
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def cmd_status() -> None:
    """Show working tree status."""
    repo_root = get_repo_root()

    # Get current commit tree (if any)
    current_commit = get_current_commit(repo_root)
    commit_tree: Dict[str, str] = current_commit["tree"] if current_commit else {}

    # Get index
    index = read_index(repo_root)

    # Get working directory files (excluding .vcs)
    working_files: Dict[str, str] = {}
    for entry in os.listdir(repo_root):
        if entry == ".vcs":
            continue
        full_path = os.path.join(repo_root, entry)
        if os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                content = f.read()
            working_files[entry] = compute_blob_hash(content)

    # Categories
    staged_new: List[str] = []
    staged_modified: List[str] = []
    staged_deleted: List[str] = []
    unstaged_modified: List[str] = []
    unstaged_deleted: List[str] = []
    untracked: List[str] = []

    all_files = set(commit_tree.keys()) | set(index.keys()) | set(working_files.keys())

    for f in sorted(all_files):
        in_commit = f in commit_tree
        in_index = f in index
        in_working = f in working_files

        commit_hash = commit_tree.get(f)
        index_hash = index.get(f)
        working_hash = working_files.get(f)

        if in_index:
            # File is staged
            if not in_commit:
                staged_new.append(f)
            elif index_hash != commit_hash:
                staged_modified.append(f)
            # else: staged but same as commit (shouldn't normally happen, but no display needed)

            # Check if working version differs from staged
            if in_working:
                if working_hash != index_hash:
                    unstaged_modified.append(f)
            else:
                # File was deleted from working tree
                unstaged_deleted.append(f)
        else:
            # Not in index
            if in_commit:
                if in_working:
                    if working_hash != commit_hash:
                        unstaged_modified.append(f)
                else:
                    unstaged_deleted.append(f)
            else:
                # Not in commit, not in index
                if in_working:
                    untracked.append(f)

    # Display
    branch_info = _get_branch_display(repo_root)
    print(f"On branch {branch_info}")

    changes_exist = False

    if staged_new or staged_modified or staged_deleted:
        changes_exist = True
        print("\nChanges staged for commit:")
        print("  (use \"vcs commit ...\" to commit)")
        for f in staged_new:
            print(f"    new file: {f}")
        for f in staged_modified:
            print(f"    modified: {f}")
        for f in staged_deleted:
            print(f"    deleted:  {f}")

    if unstaged_modified or unstaged_deleted:
        changes_exist = True
        print("\nChanges not staged for commit:")
        print("  (use \"vcs add <file>...\" to stage)")
        for f in unstaged_modified:
            print(f"    modified: {f}")
        for f in unstaged_deleted:
            print(f"    deleted:  {f}")

    if untracked:
        changes_exist = True
        print("\nUntracked files:")
        print("  (use \"vcs add <file>...\" to track)")
        for f in untracked:
            print(f"    {f}")

    if not changes_exist:
        print("nothing to commit, working tree clean")


def cmd_add(files: List[str]) -> None:
    """Stage files for the next commit."""
    repo_root = get_repo_root()
    index = read_index(repo_root)

    for file_path in files:
        full_path = os.path.join(repo_root, file_path)

        # Security: prevent path traversal
        if ".." in file_path or os.path.isabs(file_path):
            print(f"Error: invalid file path '{file_path}'", file=sys.stderr)
            continue

        if not os.path.isfile(full_path):
            print(f"Error: file not found: '{file_path}'", file=sys.stderr)
            continue

        with open(full_path, "rb") as f:
            content = f.read()

        blob_hash = store_blob(repo_root, content)
        index[file_path] = blob_hash

    write_index(repo_root, index)


def cmd_commit(message: str) -> None:
    """Create a new commit with staged changes."""
    if not message:
        print("Error: commit message is required.", file=sys.stderr)
        sys.exit(1)

    repo_root = get_repo_root()
    index = read_index(repo_root)

    if not index:
        print("Error: nothing to commit (staging area is empty).", file=sys.stderr)
        sys.exit(1)

    # Ensure all blobs exist (re-store for safety)
    for file_path, blob_hash in index.items():
        full_path = os.path.join(repo_root, file_path)
        if os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                content = f.read()
            store_blob(repo_root, content, blob_hash)

    # Build tree
    tree: Dict[str, str] = dict(index)

    # Parent commit
    parent_hash = resolve_head(repo_root)
    parents = [parent_hash] if parent_hash else []

    # Build commit data
    commit_data = {
        "tree": tree,
        "parent": parents,
        "author": get_author(),
        "timestamp": get_timestamp(),
        "message": message,
    }

    commit_hash = store_commit(repo_root, commit_data)

    # Update ref
    if is_head_detached(repo_root):
        write_head_detached(repo_root, commit_hash)
    else:
        ref_name = get_head_ref_name(repo_root)
        if ref_name is None:
            # Shouldn't happen, but fallback
            write_head_ref(repo_root, "refs/heads/master")
            ref_name = "refs/heads/master"
        write_ref(repo_root, ref_name, commit_hash)

    # Clear staging area
    clear_index(repo_root)

    print(f"[{short_hash(commit_hash)}] {message}")


def cmd_log(max_count: Optional[int] = None) -> None:
    """Show commit history."""
    repo_root = get_repo_root()
    commit_hash = resolve_head(repo_root)

    if commit_hash is None:
        print("No commits yet.")
        return

    count = 0
    visited: Set[str] = set()

    while commit_hash and (max_count is None or count < max_count):
        if commit_hash in visited:
            break
        visited.add(commit_hash)

        try:
            commit = load_commit(repo_root, commit_hash)
        except RuntimeError:
            print(f"Error: corrupt repository, commit {commit_hash} not found.", file=sys.stderr)
            break

        print(f"commit {commit_hash}")
        print(f"Author: {commit.get('author', 'unknown')}")
        print(f"Date:   {commit.get('timestamp', 'unknown')}")
        print(f"\n    {commit.get('message', '')}")
        print()

        count += 1
        parents = commit.get("parent", [])
        commit_hash = parents[0] if parents else None


def cmd_diff() -> None:
    """Show differences between working directory and last commit."""
    repo_root = get_repo_root()
    current_commit = get_current_commit(repo_root)

    if current_commit is None:
        print("No commits to diff against.")
        return

    commit_tree: Dict[str, str] = current_commit.get("tree", {})

    # Gather all relevant files
    working_files: Dict[str, bytes] = {}
    for entry in os.listdir(repo_root):
        if entry == ".vcs":
            continue
        full_path = os.path.join(repo_root, entry)
        if os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                working_files[entry] = f.read()

    all_files = set(commit_tree.keys()) | set(working_files.keys())
    any_diff = False

    for f in sorted(all_files):
        commit_blob_hash = commit_tree.get(f)
        working_content = working_files.get(f)

        if commit_blob_hash is not None and working_content is not None:
            # Both exist – compare
            working_hash = compute_blob_hash(working_content)
            if working_hash == commit_blob_hash:
                continue  # unchanged
        elif commit_blob_hash is None and working_content is None:
            continue

        any_diff = True

        # Check binary
        full_path = os.path.join(repo_root, f)
        is_bin = False

        if working_content is not None:
            is_bin = is_binary(full_path)
        elif commit_blob_hash is not None:
            # File deleted, need to check original
            old_content = load_blob(repo_root, commit_blob_hash)
            # Write temp to check? Or just check old content bytes
            if b"\x00" in old_content:
                is_bin = True
            else:
                try:
                    old_content.decode("utf-8")
                except UnicodeDecodeError:
                    is_bin = True

        if is_bin:
            if commit_blob_hash and working_content:
                print(f"Binary file {f} changed")
            elif commit_blob_hash and not working_content:
                print(f"Binary file {f} deleted")
            elif not commit_blob_hash and working_content:
                print(f"Binary file {f} added")
            print()
            continue

        # Text diff
        old_text = ""
        if commit_blob_hash:
            old_bytes = load_blob(repo_root, commit_blob_hash)
            try:
                old_text = old_bytes.decode("utf-8")
            except UnicodeDecodeError:
                old_text = old_bytes.decode("utf-8", errors="replace")

        new_text = ""
        if working_content is not None:
            try:
                new_text = working_content.decode("utf-8")
            except UnicodeDecodeError:
                new_text = working_content.decode("utf-8", errors="replace")

        diff_output = generate_unified_diff(old_text, new_text, f)
        if diff_output:
            print(f"diff --git a/{f} b/{f}")
            if commit_blob_hash and not working_content:
                print(f"--- a/{f}")
                print(f"+++ /dev/null")
            elif not commit_blob_hash and working_content:
                print(f"--- /dev/null")
                print(f"+++ b/{f}")
            else:
                print(f"--- a/{f}")
                print(f"+++ b/{f}")
            print(diff_output)
        else:
            # No text difference but hashes differ? possible for binary-like
            if commit_blob_hash and working_content:
                print(f"Binary file {f} changed")
            elif commit_blob_hash and not working_content:
                print(f"File {f} deleted")
            elif not commit_blob_hash and working_content:
                print(f"File {f} added")
            print()

    if not any_diff:
        print("No differences found.")


def cmd_checkout(commit_hash: str) -> None:
    """Restore working tree to a specific commit."""
    repo_root = get_repo_root()

    # Validate commit exists
    if not object_exists(repo_root, commit_hash):
        print(f"Error: commit '{commit_hash}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        new_commit = load_commit(repo_root, commit_hash)
    except Exception:
        print(f"Error: failed to load commit '{commit_hash}'.", file=sys.stderr)
        sys.exit(1)

    new_tree: Dict[str, str] = new_commit.get("tree", {})

    # Get old commit tree (for cleanup)
    old_commit = get_current_commit(repo_root)
    old_tree: Dict[str, str] = old_commit["tree"] if old_commit else {}

    # Remove files that are in old tree but not in new tree
    for f in old_tree:
        if f not in new_tree:
            full_path = os.path.join(repo_root, f)
            if os.path.isfile(full_path):
                os.remove(full_path)

    # Write files from new tree
    for f, blob_hash in new_tree.items():
        full_path = os.path.join(repo_root, f)
        content = load_blob(repo_root, blob_hash)
        with open(full_path, "wb") as fout:
            fout.write(content)

    # Set HEAD detached
    write_head_detached(repo_root, commit_hash)

    # Clear index (like git checkout)
    clear_index(repo_root)

    print(f"Checked out commit {short_hash(commit_hash)}.")
    print("You are in 'detached HEAD' state.")


def cmd_branch(name: str) -> None:
    """Create a new branch at the current commit."""
    repo_root = get_repo_root()

    if branch_exists(repo_root, name):
        print(f"Error: branch '{name}' already exists.", file=sys.stderr)
        sys.exit(1)

    current_hash = resolve_head(repo_root)
    if current_hash is None:
        print("Error: no commits yet. Cannot create branch without a commit.", file=sys.stderr)
        sys.exit(1)

    create_branch(repo_root, name, current_hash)
    print(f"Created branch '{name}' at {short_hash(current_hash)}.")


def cmd_switch(name: str) -> None:
    """Switch to an existing branch."""
    repo_root = get_repo_root()

    if not branch_exists(repo_root, name):
        print(f"Error: branch '{name}' not found.", file=sys.stderr)
        sys.exit(1)

    ref_path = f"refs/heads/{name}"
    new_commit_hash = read_ref(repo_root, ref_path)

    if new_commit_hash is None:
        print(f"Error: branch '{name}' has no commits.", file=sys.stderr)
        sys.exit(1)

    # Load new commit
    try:
        new_commit = load_commit(repo_root, new_commit_hash)
    except Exception:
        print(f"Error: failed to load commit for branch '{name}'.", file=sys.stderr)
        sys.exit(1)

    new_tree: Dict[str, str] = new_commit.get("tree", {})

    # Old commit
    old_commit = get_current_commit(repo_root)
    old_tree: Dict[str, str] = old_commit["tree"] if old_commit else {}

    # Remove files in old but not in new
    for f in old_tree:
        if f not in new_tree:
            full_path = os.path.join(repo_root, f)
            if os.path.isfile(full_path):
                os.remove(full_path)

    # Write files from new tree
    for f, blob_hash in new_tree.items():
        full_path = os.path.join(repo_root, f)
        content = load_blob(repo_root, blob_hash)
        with open(full_path, "wb") as fout:
            fout.write(content)

    # Update HEAD
    write_head_ref(repo_root, ref_path)

    # Clear index
    clear_index(repo_root)

    print(f"Switched to branch '{name}'.")


def _get_branch_display(repo_root: str) -> str:
    """Return a string showing the current branch / detached HEAD state."""
    if is_head_detached(repo_root):
        head_hash = read_head(repo_root)
        return f"(HEAD detached at {short_hash(head_hash)})"
    ref_name = get_head_ref_name(repo_root)
    if ref_name and ref_name.startswith("refs/heads/"):
        return ref_name[len("refs/heads/"):]
    return "unknown"
