"""Entry point for running the SSG package via `python -m ssg`."""

import sys
from ssg.cli import main

if __name__ == "__main__":
    sys.exit(main())
