#!/usr/bin/env python3

from main.server import run
import sys, traceback

if __name__ == '__main__':
    try:
        run()
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.exit(0)