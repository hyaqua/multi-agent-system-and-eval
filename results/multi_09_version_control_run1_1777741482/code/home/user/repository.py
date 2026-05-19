"""Repository class encapsulating all VCS operations."""

import json
import os
import datetime
import difflib
from typing import Optional, List, Dict, Tuple

import utils
from constants import (
    VCS_DIR,
    objects_path,
    refs_heads_path,
    head_path,
    index_path,
)


class Repository:
    """A simplified Git-like version control repository."""

    def __init__(self, repo_root: str):
        self.root = os.path.abspath(repo_root)

    # ─── helpers ──────────────────────────────────────────────────────────

    def _require_commits(self):
        """Raise if there are no commits yet."""
        head_hash, _ = utils.resolve_head(self.root)
        if head_hash is None:
            raise RuntimeError("No commits yet. Create a commit first.")

    # ─── init ─────────────────────────────────────────────────────────────

    def init(self) -> str:
        """Initialize a new VCS repository. Returns status message."""
        vcs_dir = os.path.join(self.root, VCS_DIR)
        if os.path.exists(vcs_dir):
            return f"Repository already initialized at {self.root}"

        # Create directories
        os.makedirs(os.path.join(self.root, objects_path()), exist_ok=True)
        os.makedirs(os.path.join(self.root, refs_heads_path()), exist_ok=True)

        # Write HEAD pointing to master branch
        utils.write_head_symbolic(self.root, "refs/heads/master")

        # Write empty index
        utils.write_index(self.root, {})

        return f"Initialized empty VCS repository in {vcs_dir}"

    # ─── add ──────────────────────────────────────────────────────────────

    def add(self, file_paths: List[str]) -> str:
        """
        Stage files for the next commit.
        Accepts one or more file paths relative to repo root.
        Returns status message.
        """
        index = utils.read_index(self.root)
        messages = []

        for fp in file_paths:
            abs_path = os.path.join(self.root, fp)
            if not os.path.isfile(abs_path):
                messages.append(f"warning: '{fp}' does not exist — removed from index")
                index.pop(fp, None)
                continue

            # Read file content
            try:
                with open(abs_path, "rb") as f:
                    content = f.read()
            except (IOError, OSError) as e:
                messages.append(f"error: cannot read '{fp}': {e}")
                continue

            blob_hash = utils.hash_content(content)

            # Store blob if not already stored
            if not utils.object_exists(self.root, blob_hash):
                utils.store_object(self.root, "blob", content)

            # Update index
            index[fp] = blob_hash
            messages.append(f"staged: '{fp}'")

        utils.write_index(self.root, index)
        return "\n".join(messages) if messages else "Nothing to add."

    # ─── commit ───────────────────────────────────────────────────────────

    def commit(self, message: str, author: Optional[str] = None) -> str:
        """
        Create a commit with staged files.
        Returns a message with the commit hash.
        """
        index = utils.read_index(self.root)
        if not index:
            raise RuntimeError("nothing to commit (staging area is empty)")

        if author is None:
            try:
                author = os.getlogin()
            except OSError:
                author = "unknown"

        # Resolve parent
        parent_hash, _ = utils.resolve_head(self.root)

        # Build commit object
        commit_obj = {
            "parent": parent_hash,
            "author": author,
            "timestamp": datetime.datetime.now().isoformat(),
            "message": message,
            "manifest": dict(index),
        }

        commit_json = json.dumps(commit_obj, indent=2)
        commit_bytes = commit_json.encode("utf-8")
        commit_hash = utils.store_object(self.root, "commit", commit_bytes)

        # Update branch ref or detached HEAD
        branch_ref = utils.get_current_branch_ref(self.root)
        if branch_ref:
            utils.write_branch_ref(self.root, os.path.basename(branch_ref), commit_hash)
        else:
            utils.write_head_detached(self.root, commit_hash)

        # Clear index
        utils.write_index(self.root, {})

        files_count = len(commit_obj["manifest"])
        short_hash = commit_hash[:7]
        return f"[{short_hash}] {message}\n{files_count} file(s) changed"

    # ─── status ───────────────────────────────────────────────────────────

    def status(self) -> str:
        """
        Show working directory status:
        - Staged changes (index vs HEAD)
        - Unstaged changes (working dir vs index)
        - Deleted files
        - Untracked files
        """
        index = utils.read_index(self.root)
        head_manifest = utils.get_head_manifest(self.root)
        working_files = utils.get_working_files(self.root)

        staged_new = []
        staged_modified = []
        staged_deleted = []

        # Compare index vs HEAD manifest
        all_index_paths = set(index.keys())
        all_head_paths = set(head_manifest.keys())

        for p in sorted(all_index_paths - all_head_paths):
            staged_new.append(p)
        for p in sorted(all_index_paths & all_head_paths):
            if index[p] != head_manifest[p]:
                staged_modified.append(p)
        for p in sorted(all_head_paths - all_index_paths):
            # File was in HEAD but removed from index → staged for deletion
            if p in working_files:
                # Still on disk, but removed from index
                staged_deleted.append(p)

        # Unstaged changes: working dir vs index
        unstaged_modified = []
        unstaged_deleted = []

        # All files we know about (in index or HEAD)
        tracked = set(index.keys()) | set(head_manifest.keys())

        for p in sorted(tracked):
            in_working = p in working_files
            in_index = p in index
            in_head = p in head_manifest

            if in_working:
                w_hash = working_files[p]
                if in_index:
                    if w_hash != index[p]:
                        unstaged_modified.append(p)
                elif in_head:
                    if w_hash != head_manifest[p]:
                        unstaged_modified.append(p)
            else:
                # Not in working directory
                if in_index or in_head:
                    unstaged_deleted.append(p)

        # Untracked files: on disk, not in index, not in HEAD
        untracked = sorted(
            set(working_files.keys()) - set(index.keys()) - set(head_manifest.keys())
        )

        lines = []

        if head_manifest:
            head_hash, detached = utils.resolve_head(self.root)
            branch_ref = utils.get_current_branch_ref(self.root)
            if branch_ref:
                lines.append(f"On branch {os.path.basename(branch_ref)}")
            else:
                lines.append(f"HEAD detached at {head_hash[:7] if head_hash else 'unknown'}")
        else:
            lines.append("On branch master")
            lines.append("")
            lines.append("No commits yet")

        if staged_new or staged_modified or staged_deleted:
            lines.append("")
            lines.append("Changes to be committed:")
            lines.append('  (use "commit" to record these changes)')
            lines.append("")
            for p in staged_new:
                lines.append(f"\tnew file:   {p}")
            for p in staged_modified:
                lines.append(f"\tmodified:   {p}")
            for p in staged_deleted:
                lines.append(f"\tdeleted:    {p}")

        if unstaged_modified:
            lines.append("")
            lines.append("Changes not staged for commit:")
            lines.append('  (use "add <file>..." to update what will be committed)')
            lines.append("")
            for p in unstaged_modified:
                lines.append(f"\tmodified:   {p}")

        if unstaged_deleted:
            if not unstaged_modified:
                lines.append("")
                lines.append("Changes not staged for commit:")
                lines.append('  (use "add <file>..." to update what will be committed)')
                lines.append("")
            for p in unstaged_deleted:
                lines.append(f"\tdeleted:    {p}")

        if untracked:
            lines.append("")
            lines.append("Untracked files:")
            lines.append('  (use "add <file>..." to include in what will be committed)')
            lines.append("")
            for p in untracked:
                lines.append(f"\t{p}")

        if not (staged_new or staged_modified or staged_deleted or
                unstaged_modified or unstaged_deleted or untracked):
            lines.append("nothing to commit, working tree clean")

        return "\n".join(lines)

    # ─── log ──────────────────────────────────────────────────────────────

    def log(self) -> str:
        """Display commit history."""
        head_hash, _ = utils.resolve_head(self.root)
        if head_hash is None:
            return "No commits yet."

        lines = []
        current_hash = head_hash

        while current_hash:
            try:
                obj_type, content = utils.load_object(self.root, current_hash)
                if obj_type != "commit":
                    break
                commit_data = json.loads(content.decode("utf-8"))

                lines.append(f"commit {current_hash}")
                lines.append(f"Author: {commit_data.get('author', 'unknown')}")
                lines.append(f"Date:   {commit_data.get('timestamp', 'unknown')}")
                lines.append("")
                lines.append(f"    {commit_data.get('message', '')}")
                lines.append("")

                parent = commit_data.get("parent")
                current_hash = parent if parent else None
            except (FileNotFoundError, json.JSONDecodeError, ValueError):
                break

        return "\n".join(lines).rstrip()

    # ─── diff ─────────────────────────────────────────────────────────────

    def diff(self) -> str:
        """
        Show line-by-line differences between working directory and HEAD commit.
        Binary files are reported but not diffed.
        """
        head_manifest = utils.get_head_manifest(self.root)
        working_files = utils.get_working_files(self.root)

        all_files = sorted(set(head_manifest.keys()) | set(working_files.keys()))

        if not all_files:
            return "No files to diff."

        lines = []
        for rel_path in all_files:
            in_working = rel_path in working_files
            in_head = rel_path in head_manifest

            # Get content
            working_content = None
            head_content = None

            abs_path = os.path.join(self.root, rel_path)
            if in_working:
                try:
                    with open(abs_path, "rb") as f:
                        working_content = f.read()
                except (IOError, OSError):
                    working_content = None

            if in_head:
                try:
                    _, head_content = utils.load_object(self.root, head_manifest[rel_path])
                except (FileNotFoundError, ValueError):
                    head_content = None

            # If neither has content, skip
            if working_content is None and head_content is None:
                continue

            # Same content?
            if working_content is not None and head_content is not None:
                if working_content == head_content:
                    continue

            # Check binary
            w_binary = utils.is_binary_content(working_content) if working_content else False
            h_binary = utils.is_binary_content(head_content) if head_content else False

            if w_binary or h_binary:
                if not in_head:
                    lines.append(f"Binary file {rel_path} added")
                elif not in_working:
                    lines.append(f"Binary file {rel_path} deleted")
                else:
                    lines.append(f"Binary files {rel_path} differ")
                continue

            # Text diff
            w_text = working_content.decode("utf-8", errors="replace").splitlines(keepends=True) if working_content else []
            h_text = head_content.decode("utf-8", errors="replace").splitlines(keepends=True) if head_content else []

            diff_lines = list(difflib.unified_diff(
                h_text, w_text,
                fromfile=f"a/{rel_path}" if in_head else f"a/{rel_path}",
                tofile=f"b/{rel_path}" if in_working else f"b/{rel_path}",
            ))

            if diff_lines:
                lines.extend(diff_lines)

        return "\n".join(lines) if lines else "No changes."

    # ─── checkout ─────────────────────────────────────────────────────────

    def checkout(self, commit_hash: str) -> str:
        """
        Restore working directory to the state of a given commit.
        Accepts full or abbreviated hash.
        """
        # Resolve abbreviated hash
        resolved_hash = self._resolve_hash(commit_hash)
        if resolved_hash is None:
            raise RuntimeError(f"Commit '{commit_hash}' not found.")

        try:
            obj_type, content = utils.load_object(self.root, resolved_hash)
            if obj_type != "commit":
                raise RuntimeError(f"Object '{resolved_hash[:7]}' is not a commit.")
        except FileNotFoundError:
            raise RuntimeError(f"Commit '{commit_hash}' not found.")

        commit_data = json.loads(content.decode("utf-8"))
        manifest = commit_data.get("manifest", {})

        # Write files from manifest
        for rel_path, blob_hash in manifest.items():
            abs_path = os.path.join(self.root, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            try:
                _, blob_content = utils.load_object(self.root, blob_hash)
                with open(abs_path, "wb") as f:
                    f.write(blob_content)
            except (FileNotFoundError, ValueError) as e:
                raise RuntimeError(f"Could not restore '{rel_path}': {e}")

        # Detach HEAD to this commit
        utils.write_head_detached(self.root, resolved_hash)

        short = resolved_hash[:7]
        return f"HEAD is now at {short} — {commit_data.get('message', '')}"

    # ─── branch ───────────────────────────────────────────────────────────

    def branch(self, name: str) -> str:
        """Create a new branch at the current HEAD commit."""
        head_hash, _ = utils.resolve_head(self.root)
        if head_hash is None:
            raise RuntimeError("Cannot create branch: no commits yet.")

        # Check if branch already exists
        if utils.read_branch_ref(self.root, name) is not None:
            raise RuntimeError(f"Branch '{name}' already exists.")

        utils.write_branch_ref(self.root, name, head_hash)
        return f"Created branch '{name}' at {head_hash[:7]}"

    # ─── switch ───────────────────────────────────────────────────────────

    def switch(self, name: str) -> str:
        """Switch to an existing branch."""
        commit_hash = utils.read_branch_ref(self.root, name)
        if commit_hash is None:
            raise RuntimeError(f"Branch '{name}' does not exist.")

        # Load commit manifest
        try:
            obj_type, content = utils.load_object(self.root, commit_hash)
            if obj_type != "commit":
                raise RuntimeError(f"Branch '{name}' points to non-commit object.")
        except FileNotFoundError:
            raise RuntimeError(f"Commit for branch '{name}' not found.")

        commit_data = json.loads(content.decode("utf-8"))
        manifest = commit_data.get("manifest", {})

        # Write files from manifest
        for rel_path, blob_hash in manifest.items():
            abs_path = os.path.join(self.root, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            try:
                _, blob_content = utils.load_object(self.root, blob_hash)
                with open(abs_path, "wb") as f:
                    f.write(blob_content)
            except (FileNotFoundError, ValueError) as e:
                raise RuntimeError(f"Could not restore '{rel_path}': {e}")

        # Set symbolic HEAD
        ref_path = f"refs/heads/{name}"
        utils.write_head_symbolic(self.root, ref_path)

        return f"Switched to branch '{name}'"

    # ─── resolve abbreviated hash ─────────────────────────────────────────

    def _resolve_hash(self, short_hash: str) -> Optional[str]:
        """
        Resolve a full or abbreviated commit hash.
        Returns the full hash string, or None if not found.
        """
        if utils.object_exists(self.root, short_hash):
            return short_hash

        # Try to find by prefix in objects directory
        obj_dir = os.path.join(self.root, objects_path())
        if len(short_hash) < 2:
            return None

        prefix_dir = os.path.join(obj_dir, short_hash[:2])
        if not os.path.isdir(prefix_dir):
            return None

        rest = short_hash[2:]
        candidates = []
        for fname in os.listdir(prefix_dir):
            full = short_hash[:2] + fname
            if full.startswith(short_hash):
                candidates.append(full)

        if len(candidates) == 1:
            return candidates[0]
        return None
