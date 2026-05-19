"""Utility functions: hashing, binary detection, unified diff generation."""

import hashlib
import difflib
import os


def compute_blob_hash(content: bytes) -> str:
    """Compute content-addressable hash for a blob.

    Follows Git-like format: SHA256("blob <size>\\0<content>")
    """
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha256(header + content).hexdigest()


def compute_commit_hash(commit_json: bytes) -> str:
    """Compute content-addressable hash for a commit.

    Follows Git-like format: SHA256("commit <size>\\0<json>")
    """
    header = f"commit {len(commit_json)}\0".encode("utf-8")
    return hashlib.sha256(header + commit_json).hexdigest()


def is_binary(file_path: str) -> bool:
    """Check whether a file appears to be binary.

    Reads up to 1024 bytes and checks for null bytes or non-UTF-8-decodable content.
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
    except (OSError, IOError):
        return False

    if b"\x00" in chunk:
        return True

    try:
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def generate_unified_diff(
    old_text: str, new_text: str, filename: str, context_lines: int = 3
) -> str:
    """Generate a unified diff between old and new text for the given filename."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=context_lines,
    )
    return "".join(diff)


def short_hash(full_hash: str, length: int = 7) -> str:
    """Return a shortened version of a hash for display."""
    return full_hash[:length]
