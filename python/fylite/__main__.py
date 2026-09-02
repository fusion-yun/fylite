"""``python -m fylite`` — the same entry point as the ``fylite`` script."""
import sys

from .engine import cli_main

if __name__ == "__main__":
    sys.exit(cli_main())
