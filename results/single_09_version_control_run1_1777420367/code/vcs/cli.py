"""Command-line interface for VCS."""

import sys
import argparse
from vcs.repo import Repository, find_repo_root


def main():
    parser = argparse.ArgumentParser(
        prog="vcs",
        description="Simplified Git-like version control system",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- init ----
    p_init = subparsers.add_parser("init", help="Initialize a new repository")
    p_init.add_argument("path", nargs="?", default=None,
                        help="Path to initialize (default: current directory)")

    # ---- status ----
    subparsers.add_parser("status", help="Show working-tree status")

    # ---- add ----
    p_add = subparsers.add_parser("add", help="Stage files for next commit")
    p_add.add_argument("files", nargs="+", help="Files to stage")

    # ---- commit ----
    p_commit = subparsers.add_parser("commit", help="Create a new commit")
    p_commit.add_argument("-m", "--message", required=True,
                          help="Commit message")

    # ---- log ----
    p_log = subparsers.add_parser("log", help="Show commit history")
    p_log.add_argument("-n", "--max-count", type=int, default=0,
                       help="Limit number of commits shown")

    # ---- diff ----
    subparsers.add_parser("diff", help="Show diff between working dir and last commit")

    # ---- checkout ----
    p_checkout = subparsers.add_parser("checkout", help="Restore files to a commit")
    p_checkout.add_argument("commit", help="Commit hash (full or abbreviated)")

    # ---- branch ----
    p_branch = subparsers.add_parser("branch", help="Create or list branches")
    p_branch.add_argument("name", nargs="?", default=None,
                          help="Branch name to create")
    p_branch.add_argument("-d", "--delete", default=None,
                          help="Delete a branch")

    # ---- switch ----
    p_switch = subparsers.add_parser("switch", help="Switch to a branch")
    p_switch.add_argument("branch", help="Branch name to switch to")

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    if args.command == "init":
        import os
        path = None
        if args.path:
            path = __import__("pathlib").Path(args.path).resolve()
        repo = Repository.init(path)

    elif args.command == "status":
        repo = Repository.load()
        repo.status()

    elif args.command == "add":
        repo = Repository.load()
        repo.add(args.files)

    elif args.command == "commit":
        repo = Repository.load()
        repo.commit(args.message)

    elif args.command == "log":
        repo = Repository.load()
        repo.log(args.max_count)

    elif args.command == "diff":
        repo = Repository.load()
        repo.diff()

    elif args.command == "checkout":
        repo = Repository.load()
        repo.checkout(args.commit)

    elif args.command == "branch":
        repo = Repository.load()
        repo.branch(name=args.name, delete=args.delete,
                    list_branches=(args.name is None and args.delete is None))

    elif args.command == "switch":
        repo = Repository.load()
        repo.switch(args.branch)


if __name__ == "__main__":
    main()
