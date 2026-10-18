#!/usr/bin/env python3
"""Telegram Robot Leads safe runtime.

This runtime intentionally contains no group discovery, participant scraping,
anti-detection/human-mimic behaviour, or unsolicited bulk-add pipeline.
It only processes operator-managed allowlists and explicitly approved users.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from safe_runtime import main


if __name__ == "__main__":
    raise SystemExit(main())
