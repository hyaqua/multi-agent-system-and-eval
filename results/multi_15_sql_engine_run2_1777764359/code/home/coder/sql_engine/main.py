#!/usr/bin/env python3
"""Entry point for the SQL Query Engine REPL."""

import sys
import os

# Ensure the project directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from repl import run_repl

if __name__ == '__main__':
    run_repl()
