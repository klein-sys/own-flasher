#!/usr/bin/env python3
"""
FlashDock — Entry point.

Run with:  python main.py
"""

import sys


def main() -> None:
    from flashdock.app import run
    sys.exit(run())


if __name__ == "__main__":
    main()
