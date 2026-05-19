#!/usr/bin/env python3
"""system_monitor_tui - A terminal-based system monitor in the style of htop.

Usage:
    python system_monitor_tui/main.py [--interval SECONDS]
    python -m system_monitor_tui.main [--interval SECONDS]
"""

import argparse
import sys

from system_monitor_tui.ui import SystemMonitorUI


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal-based system monitor (htop-style)"
    )
    parser.add_argument(
        '--interval', '-i',
        type=float,
        default=1.0,
        help='Update interval in seconds (default: 1.0)'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.interval < 0.1:
        print("Interval must be at least 0.1 seconds")
        sys.exit(1)

    try:
        ui = SystemMonitorUI(interval=args.interval)
        ui.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
