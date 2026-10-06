#!/usr/bin/env python3
"""Convenience runner script for NAS-Pulse."""

import sys
from pathlib import Path

# Ensure local package is in sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from nas_pulse.cli import main

if __name__ == "__main__":
    sys.exit(main())
