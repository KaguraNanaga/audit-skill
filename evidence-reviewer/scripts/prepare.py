#!/usr/bin/env python3
"""Compatibility entry for the existing stage-0 inventory command."""
from core.prepare import main

if __name__ == "__main__":
    raise SystemExit(main())
