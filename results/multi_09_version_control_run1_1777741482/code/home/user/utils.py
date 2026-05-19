"""Utility functions for the VCS: hashing, storage, binary detection."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict

from constants import (
    VCS_DIR,
    objects_path,
    refs_heads_path,
    head_path,
    index_path,
)


def hash_content(content: bytes) -> str:
    """Return SHA-1 hex digest of the given content."""
    return hashlib.sha1(content).hexdigest()


def hash_file(filepath: str) -> str:
    """Read a file and return its SHA-1 hash."""
    with open(filepath, "rb") as f:
        return hash_content(f.read())


def store_object(repo_root: str, obj_type: str, content: bytes) -> str:
    """
    Store an object in the content-addressable store.
    Returns the SHA-1 hash of the content.
    
    Object format stored on disk:
      <type>\n<content>
    (type + newline + raw content)
    """
    h = hash_content(content)
    obj_dir = os.path.join(repo_root, objects_path(), h[:2])
    obj_file = os.path.join(obj_dir, h[2:])

    os.makedirs(obj_dir, exist_ok=True)

    # Store as: type\n<raw_content>
    header = (obj_type + "\n").encode("utf-8")
    with open(obj_file, "wb") as f:
        f.write(header + content)

    return h


def load_object(repo_root: str, obj_hash: str) -> Tuple[str, bytes]:
    """
    Load an object from the store by its hash.
    Returns (type, content_bytes).
    """
    obj_dir = os.path.join(repo_root, objects_path(), obj_hash[:2])
    obj_file = os.path.join(obj_dir, obj_hash[2:])

    if not os.path.isfile(obj_file):
        raise FileNotFoundError(f"Object not found: {obj_hash}")

    with open(obj_file, "rb") as f:
        data = f.read()

    # Split on first newline to get type
    newline_pos = data.find(b"\n")
    if newline_pos == -1:
        raise ValueError(f"Corrupt object: {obj_hash}")

    obj_type = data[:newline_pos].decode("utf-8")
    content = data[newline_pos + 1:]

    return obj_type, content


def object_exists(repo_root: str, obj_hash: str) -> bool:
    """Check if an object with the given hash exists."""
    obj_dir = os.path.join(repo_root, objects_path(), obj_hash[:2])
    obj_file = os.path.join(obj_dir, obj_hash[2:])
    return os.path.isfile(obj_file)


def is_binary(filepath: str) -> bool:
    """
    Heuristic: read up to 8KB and check for null bytes.
    Returns True if binary.
    """
    if not os.path.isfile(filepath):
        return False
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
    except (IOError, OSError):
        return False
    return b"\x00" in chunk


def is_binary_content(content: bytes) -> bool:
    """Check if bytes content is binary by looking for null bytes."""
    return b"\x00" in content[:8192]


def get_working_files(repo_root: str) -> Dict[str, str]:
    """
    Walk the working directory (excluding .vcs) and return
    a dict mapping relative path → SHA-1 hash of file content.
    """
    result = {}
    vcs_abs = os.path.join(repo_root, VCS_DIR)
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip .vcs directory
        if os.path.abspath(dirpath).startswith(os.path.abspath(vcs_abs)):
            continue
        # Skip any directory starting with .vcs just in case
        if VCS_DIR in dirnames:
            dirnames.remove(VCS_DIR)

        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, repo_root)
            try:
                result[rel_path] = hash_file(full_path)
            except (IOError, OSError):
                # Skip unreadable files
                continue
    return result


def read_index(repo_root: str) -> Dict[str, str]:
    """Read the staging index file. Returns {path: blob_hash}."""
    idx_path = os.path.join(repo_root, index_path())
    if not os.path.isfile(idx_path):
        return {}
    try:
        with open(idx_path, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def write_index(repo_root: str, index_data: Dict[str, str]) -> None:
    """Write the staging index file."""
    idx_path = os.path.join(repo_root, index_path())
    with open(idx_path, "w") as f:
        json.dump(index_data, f, indent=2)


def resolve_head(repo_root: str) -> Tuple[Optional[str], bool]:
    """
    Resolve HEAD to a commit hash.
    Returns (commit_hash_or_None, is_detached).
    
    HEAD file contains either:
      ref: refs/heads/<branch_name>   → symbolic ref
      <commit_hash>                   → detached HEAD
    """
    h_path = os.path.join(repo_root, head_path())
    if not os.path.isfile(h_path):
        return None, False

    with open(h_path, "r") as f:
        head_content = f.read().strip()

    if head_content.startswith("ref: "):
        ref_path = head_content[5:]
        full_ref = os.path.join(repo_root, ref_path)
        if os.path.isfile(full_ref):
            with open(full_ref, "r") as rf:
                commit_hash = rf.read().strip()
            return commit_hash if commit_hash else None, False
        else:
            return None, False
    else:
        # Detached HEAD: content is a commit hash
        return head_content if head_content else None, True


def get_current_branch_ref(repo_root: str) -> Optional[str]:
    """
    Get the current branch reference path (e.g. 'refs/heads/master')
    from HEAD, or None if detached.
    """
    h_path = os.path.join(repo_root, head_path())
    if not os.path.isfile(h_path):
        return None

    with open(h_path, "r") as f:
        head_content = f.read().strip()

    if head_content.startswith("ref: "):
        return head_content[5:]
    return None


def write_head_detached(repo_root: str, commit_hash: str) -> None:
    """Write HEAD as a detached commit hash."""
    h_path = os.path.join(repo_root, head_path())
    with open(h_path, "w") as f:
        f.write(commit_hash + "\n")


def write_head_symbolic(repo_root: str, ref_path: str) -> None:
    """Write HEAD as a symbolic ref."""
    h_path = os.path.join(repo_root, head_path())
    with open(h_path, "w") as f:
        f.write(f"ref: {ref_path}\n")


def write_branch_ref(repo_root: str, branch_name: str, commit_hash: str) -> None:
    """Write a branch reference file."""
    ref_path = os.path.join(repo_root, refs_heads_path(), branch_name)
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, "w") as f:
        f.write(commit_hash + "\n")


def read_branch_ref(repo_root: str, branch_name: str) -> Optional[str]:
    """Read a branch reference file, returning the commit hash or None."""
    ref_path = os.path.join(repo_root, refs_heads_path(), branch_name)
    if not os.path.isfile(ref_path):
        return None
    with open(ref_path, "r") as f:
        return f.read().strip()


def find_repo_root(start_path: str = ".") -> Optional[str]:
    """
    Walk up from start_path until we find a .vcs directory.
    Returns the repo root path or None.
    """
    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, VCS_DIR)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            # Reached root filesystem
            return None
        current = parent


def get_head_manifest(repo_root: str) -> Dict[str, str]:
    """
    Get the manifest (file-to-blob mapping) from the HEAD commit.
    Returns empty dict if no HEAD commit.
    """
    head_hash, _ = resolve_head(repo_root)
    if head_hash is None:
        return {}

    try:
        obj_type, content = load_object(repo_root, head_hash)
        if obj_type != "commit":
            return {}
        commit_data = json.loads(content.decode("utf-8"))
        return commit_data.get("manifest", {})
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return {}
