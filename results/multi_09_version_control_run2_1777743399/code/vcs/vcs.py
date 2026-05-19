#!/usr/bin/env python3
"""vcs – A simple Git-like version control system.

Usage:
    vcs init                     Initialize a new repository
    vcs status                   Show working tree status
    vcs add <file>...            Stage files for commit
    vcs commit <message>         Commit staged changes
    vcs log                      Show commit history
    vcs diff                     Show unstaged changes
    vcs checkout <commit-hash>   Restore working tree to a commit
    vcs branch <name>            Create a new branch
    vcs switch <name>            Switch to an existing branch
"""

import sys

from repository import is_initialized
from commands import (
    cmd_init,
    cmd_status,
    cmd_add,
    cmd_commit,
    cmd_log,
    cmd_diff,
    cmd_checkout,
    cmd_branch,
    cmd_switch,
)


COMMANDS_REQUIRING_REPO = {
    "status", "add", "commit", "log", "diff",
    "checkout", "branch", "switch",
}


def print_usage() -> None:
    """Print usage information."""
    print(__doc__)


def main() -> None:
    """Entry point for the vcs CLI."""
    args = sys.argv[1:]

    if not args:
        print_usage()
        sys.exit(0)

    command = args[0]

    # Handle help
    if command in ("-h", "--help", "help"):
        print_usage()
        sys.exit(0)

    # Validate command
    valid_commands = COMMANDS_REQUIRING_REPO | {"init"}
    if command not in valid_commands:
        print(f"Error: unknown command '{command}'.", file=sys.stderr)
        print_usage()
        sys.exit(1)

    # Check for repository (except for init)
    if command in COMMANDS_REQUIRING_REPO:
        if not is_initialized():
            print("Error: not a vcs repository (or .vcs not found).", file=sys.stderr)
            sys.exit(1)

    # Dispatch
    try:
        if command == "init":
            cmd_init()

        elif command == "status":
            cmd_status()

        elif command == "add":
            if len(args) < 2:
                print("Error: no files specified.", file=sys.stderr)
                print("Usage: vcs add <file>...", file=sys.stderr)
                sys.exit(1)
            cmd_add(args[1:])

        elif command == "commit":
            # Message is everything after "commit"
            message = " ".join(args[1:]) if len(args) > 1 else ""
            cmd_commit(message)

        elif command == "log":
            cmd_log()

        elif command == "diff":
            cmd_diff()

        elif command == "checkout":
            if len(args) < 2:
                print("Error: commit hash required.", file=sys.stderr)
                print("Usage: vcs checkout <commit-hash>", file=sys.stderr)
                sys.exit(1)
            cmd_checkout(args[1])

        elif command == "branch":
            if len(args) < 2:
                print("Error: branch name required.", file=sys.stderr)
                print("Usage: vcs branch <name>", file=sys.stderr)
                sys.exit(1)
            cmd_branch(args[1])

        elif command == "switch":
            if len(args) < 2:
                print("Error: branch name required.", file=sys.stderr)
                print("Usage: vcs switch <name>", file=sys.stderr)
                sys.exit(1)
            cmd_switch(args[1])

        else:
            print(f"Error: unknown command '{command}'.", file=sys.stderr)
            sys.exit(1)

    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
