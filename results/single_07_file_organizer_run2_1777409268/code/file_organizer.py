#!/usr/bin/env python3
"""Convenience wrapper: run `python file_organizer.py <args>`."""

import sys
import os

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from file_organizer.cli import main

if __name__ == "__main__":
    main()
