"""Core repository operations: init, object/blob storage, refs, index, commits."""

import json
import os
from datetime import datetime, timezone
from typing import Optional, Dict, List

from utils import compute_blob_hash, compute_commit_hash


# Default paths relative to repository root
VCS_DIR = ".vcs"
OBJECTS_DIR = os.path.join(VCS_DIR, "objects")
REFS_DIR = os.path.join(VCS_DIR, "refs")
HEADS_DIR = os.path.join(REFS_DIR, "heads")
HEAD_FILE = os.path.join(VCS_DIR, "HEAD")
INDEX_FILE = os.path.join(VCS_DIR, "index.json")


def find_repo_root() -> Optional[str]:
    """Walk up from cwd to find the .vcs directory. Returns path or None."""
    cwd = os.getcwd()
    while True:
        if os.path.isdir(os.path.join(cwd, VCS_DIR)):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            return None
        cwd = parent


def is_initialized() -> bool:
    """Check if the current directory (or a parent) contains a .vcs repo."""
    return find_repo_root() is not None


def get_repo_root() -> str:
    """Get the repository root directory. Raises if not initialized."""
    root = find_repo_root()
    if root is None:
        raise RuntimeError("Error: not a vcs repository (or .vcs not found).")
    return root


def init_repository() -> str:
    """Initialize a new .vcs repository in the current directory.

    Returns the path to the repo root.
    """
    root = os.getcwd()
    vcs_path = os.path.join(root, VCS_DIR)

    if os.path.exists(vcs_path):
        raise RuntimeError("Repository already exists.")

    os.makedirs(os.path.join(root, OBJECTS_DIR), exist_ok=True)
    os.makedirs(os.path.join(root, HEADS_DIR), exist_ok=True)

    # HEAD initially points to master branch (which doesn't exist yet)
    write_head_ref(root, "refs/heads/master")

    # Empty index
    write_index(root, {})

    return root


# ---------------------------------------------------------------------------
# Object storage
# ---------------------------------------------------------------------------

def object_path(repo_root: str, obj_hash: str) -> str:
    """Return the filesystem path for an object given its hash."""
    return os.path.join(repo_root, OBJECTS_DIR, obj_hash[:2], obj_hash[2:])


def object_exists(repo_root: str, obj_hash: str) -> bool:
    """Check if an object with the given hash already exists."""
    return os.path.isfile(object_path(repo_root, obj_hash))


def store_object(repo_root: str, content: bytes, obj_hash: str) -> None:
    """Store an object in the objects directory.

    If the object already exists, this is a no-op (content-addressable dedup).
    """
    path = object_path(repo_root, obj_hash)
    if os.path.isfile(path):
        return  # already stored
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def load_object(repo_root: str, obj_hash: str) -> bytes:
    """Load the raw content of an object by its hash."""
    path = object_path(repo_root, obj_hash)
    if not os.path.isfile(path):
        raise RuntimeError(f"Object not found: {obj_hash}")
    with open(path, "rb") as f:
        return f.read()


def store_blob(repo_root: str, content: bytes) -> str:
    """Compute hash, store blob object, return the hash."""
    blob_hash = compute_blob_hash(content)
    store_object(repo_root, content, blob_hash)
    return blob_hash


def load_blob(repo_root: str, blob_hash: str) -> bytes:
    """Load the content of a blob."""
    return load_object(repo_root, blob_hash)


def store_commit(repo_root: str, commit_data: dict) -> str:
    """Serialize, hash, and store a commit object. Return commit hash."""
    commit_json = json.dumps(commit_data, ensure_ascii=False, indent=2)
    commit_bytes = commit_json.encode("utf-8")
    commit_hash = compute_commit_hash(commit_bytes)
    store_object(repo_root, commit_bytes, commit_hash)
    return commit_hash


def load_commit(repo_root: str, commit_hash: str) -> dict:
    """Load and parse a commit object, returning the commit data dict."""
    raw = load_object(repo_root, commit_hash)
    return json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# HEAD
# ---------------------------------------------------------------------------

def read_head(repo_root: str) -> str:
    """Read HEAD file. Returns either 'ref: refs/heads/<name>' or a commit hash."""
    with open(os.path.join(repo_root, HEAD_FILE), "r") as f:
        return f.read().strip()


def write_head_ref(repo_root: str, ref_path: str) -> None:
    """Set HEAD to point to a reference (e.g., 'refs/heads/master')."""
    with open(os.path.join(repo_root, HEAD_FILE), "w") as f:
        f.write(f"ref: {ref_path}\n")


def write_head_detached(repo_root: str, commit_hash: str) -> None:
    """Set HEAD directly to a commit hash (detached HEAD)."""
    with open(os.path.join(repo_root, HEAD_FILE), "w") as f:
        f.write(commit_hash + "\n")


def is_head_detached(repo_root: str) -> bool:
    """Return True if HEAD is detached (points directly to a commit hash)."""
    head = read_head(repo_root)
    return not head.startswith("ref: ")


def get_head_ref_name(repo_root: str) -> Optional[str]:
    """If HEAD points to a branch ref, return the ref path. Else None."""
    head = read_head(repo_root)
    if head.startswith("ref: "):
        return head[5:]  # e.g., "refs/heads/master"
    return None


def resolve_head(repo_root: str) -> Optional[str]:
    """Resolve HEAD to a commit hash, or None if no commit exists yet."""
    head = read_head(repo_root)
    if head.startswith("ref: "):
        ref_path = head[5:]
        return read_ref(repo_root, ref_path)
    else:
        # Detached – the head content IS the commit hash
        if head:
            return head
        return None


# ---------------------------------------------------------------------------
# Refs
# ---------------------------------------------------------------------------

def read_ref(repo_root: str, ref_path: str) -> Optional[str]:
    """Read a reference file (e.g., 'refs/heads/master'). Return commit hash or None."""
    full_path = os.path.join(repo_root, ref_path)
    if not os.path.isfile(full_path):
        return None
    with open(full_path, "r") as f:
        return f.read().strip()


def write_ref(repo_root: str, ref_path: str, commit_hash: str) -> None:
    """Write a reference file with the given commit hash."""
    full_path = os.path.join(repo_root, ref_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(commit_hash + "\n")


def create_branch(repo_root: str, branch_name: str, commit_hash: str) -> None:
    """Create a new branch pointing to the given commit."""
    write_ref(repo_root, f"refs/heads/{branch_name}", commit_hash)


def branch_exists(repo_root: str, branch_name: str) -> bool:
    """Check if a branch exists."""
    return os.path.isfile(os.path.join(repo_root, HEADS_DIR, branch_name))


def list_branches(repo_root: str) -> List[str]:
    """Return a list of branch names."""
    heads_dir = os.path.join(repo_root, HEADS_DIR)
    if not os.path.isdir(heads_dir):
        return []
    return sorted(os.listdir(heads_dir))


# ---------------------------------------------------------------------------
# Index (staging area)
# ---------------------------------------------------------------------------

def read_index(repo_root: str) -> Dict[str, str]:
    """Read the staging index (file_path -> blob_hash)."""
    path = os.path.join(repo_root, INDEX_FILE)
    if not os.path.isfile(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def write_index(repo_root: str, index: Dict[str, str]) -> None:
    """Write the staging index."""
    path = os.path.join(repo_root, INDEX_FILE)
    with open(path, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def clear_index(repo_root: str) -> None:
    """Reset the index to an empty dict."""
    write_index(repo_root, {})


# ---------------------------------------------------------------------------
# Commit helpers
# ---------------------------------------------------------------------------

def get_current_commit(repo_root: str) -> Optional[dict]:
    """Return the current commit data dict, or None if no commits exist."""
    commit_hash = resolve_head(repo_root)
    if commit_hash is None:
        return None
    return load_commit(repo_root, commit_hash)


def get_current_commit_hash(repo_root: str) -> Optional[str]:
    """Return the current commit hash, or None."""
    return resolve_head(repo_root)


def get_author() -> str:
    """Get the author name from environment, defaulting to 'unknown'."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def get_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
