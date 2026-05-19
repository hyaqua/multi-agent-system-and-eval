"""Entry point: python -m csv_pipeline or python csv_pipeline/__main__.py"""
import sys
from pathlib import Path

if __name__ == '__main__' and __package__ is None:
    # Running as `python csv_pipeline/__main__.py` without -m flag.
    # Make the package parent importable and set __package__.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = 'csv_pipeline'

from csv_pipeline.cli import main

if __name__ == "__main__":
    sys.exit(main() or 0)
