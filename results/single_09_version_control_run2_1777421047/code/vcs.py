#!/usr/bin/env python3
"""VCS – a simplified Git-like version control system."""

import argparse
import sys
from repo import Repository


def main():
    parser = argparse.ArgumentParser(
        prog='vcs',
        description='VCS – Simple Version Control System',
    )
    sub = parser.add_subparsers(dest='command', help='Subcommands')

    # init
    sub.add_parser('init', help='Initialize a new repository')

    # status
    sub.add_parser('status', help='Show working tree status')

    # add
    p_add = sub.add_parser('add', help='Stage files for the next commit')
    p_add.add_argument('files', nargs='+', help='Files to stage')

    # commit
    p_commit = sub.add_parser('commit', help='Create a new commit with staged changes')
    p_commit.add_argument('-m', '--message', required=True, help='Commit message')

    # log
    sub.add_parser('log', help='Show commit history')

    # diff
    sub.add_parser('diff', help='Show line-by-line diff vs last commit')

    # checkout
    p_checkout = sub.add_parser('checkout', help='Restore files to a specific commit')
    p_checkout.add_argument('commit', help='Commit hash (full or partial prefix)')

    # branch
    p_branch = sub.add_parser('branch', help='List branches or create a new one')
    p_branch.add_argument('name', nargs='?', default=None,
                          help='Branch name (omit to list)')

    # switch
    p_switch = sub.add_parser('switch', help='Switch to a different branch')
    p_switch.add_argument('name', help='Branch name')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

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
