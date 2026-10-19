#!/usr/bin/env python3
"""Telegram Robot Leads safe runtime.

This runtime can discover public group handles by topic (not participants).
It never scrapes member identities, imitates people or bulk-adds users.
Joining groups and adding members require explicit authorization.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from safe_runtime import main


if __name__ == "__main__":
    raise SystemExit(main())
