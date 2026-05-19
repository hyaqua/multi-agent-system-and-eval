#!/usr/bin/env python3
"""vcs: A simplified Git-like version control system."""

import argparse
import sys
import os

from repository import Repository
from utils import find_repo_root


def require_repo():
    """Find the repository root. Exit with error if not in a repo."""
    repo_root = find_repo_root()
    if repo_root is None:
        print("fatal: not a VCS repository (or any of the parent directories): .vcs",
              file=sys.stderr)
        sys.exit(1)
    return repo_root


def cmd_init(args):
    """Initialize a new repository."""
    repo = Repository(os.getcwd())
    try:
        msg = repo.init()
        print(msg)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add(args):
    """Stage files for commit."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        msg = repo.add(args.files)
        if msg:
            print(msg)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_commit(args):
    """Commit staged changes."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        msg = repo.commit(args.message, args.author)
        print(msg)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show working tree status."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        print(repo.status())
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_log(args):
    """Show commit log."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        print(repo.log())
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_diff(args):
    """Show diff between working directory and HEAD."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        output = repo.diff()
        if output:
            print(output)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkout(args):
    """Checkout a specific commit."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        msg = repo.checkout(args.commit)
        print(msg)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_branch(args):
    """Create a new branch."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        msg = repo.branch(args.name)
        print(msg)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_switch(args):
    """Switch to a branch."""
    repo_root = require_repo()
    repo = Repository(repo_root)
    try:
        msg = repo.switch(args.name)
        print(msg)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="vcs",
        description="A simplified Git-like version control system",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new repository")

    # add
    p_add = subparsers.add_parser("add", help="Stage files for commit")
    p_add.add_argument("files", nargs="+", help="Files to stage")

    # commit
    p_commit = subparsers.add_parser("commit", help="Commit staged changes")
    p_commit.add_argument("-m", "--message", required=True, help="Commit message")
    p_commit.add_argument("--author", default=None, help="Commit author (default: system user)")

    # status
    p_status = subparsers.add_parser("status", help="Show working tree status")

    # log
    p_log = subparsers.add_parser("log", help="Show commit history")

    # diff
    p_diff = subparsers.add_parser("diff", help="Show changes between working directory and HEAD")

    # checkout
    p_checkout = subparsers.add_parser("checkout", help="Restore working tree to a commit")
    p_checkout.add_argument("commit", help="Commit hash (full or abbreviated)")

    # branch
    p_branch = subparsers.add_parser("branch", help="Create a new branch")
    p_branch.add_argument("name", help="Branch name")

    # switch
    p_switch = subparsers.add_parser("switch", help="Switch to a branch")
    p_switch.add_argument("name", help="Branch name")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    dispatch = {
        "init": cmd_init,
        "add": cmd_add,
        "commit": cmd_commit,
        "status": cmd_status,
        "log": cmd_log,
        "diff": cmd_diff,
        "checkout": cmd_checkout,
        "branch": cmd_branch,
        "switch": cmd_switch,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
