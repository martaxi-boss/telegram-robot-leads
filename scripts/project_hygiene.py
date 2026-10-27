#!/usr/bin/env python3
"""Bounded cleanup of generated Python bytecode in Telegram Robot Leads only.

This tool NEVER deletes user accounts, sessions, sqlite databases, event
journals, operation state, logs, backups, virtualenvs, unrelated project files,
or the program's source. Default mode is a read-only dry run.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

CANONICAL_ROOT = Path("/opt/telegram-robot-leads")
ALLOWED_PARENTS = (Path("."), Path("scripts"), Path("tests"))
CACHE_NAME = "__pycache__"
ALLOWED_EXTENSIONS = {".pyc", ".pyo"}
MAX_CACHE_FILE_BYTES = 16 * 1024 * 1024


class HygieneBlocked(RuntimeError):
    pass


def _require_owned_directory(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise HygieneBlocked("directory_unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or path.is_symlink()):
        raise HygieneBlocked("directory_not_private_owned")


def plan(root: Path) -> list[Path]:
    """Inventory only the three literal root-level Python cache locations."""
    if not root.is_absolute() or root.resolve() != root or root.is_symlink():
        raise HygieneBlocked("root_invalid")
    _require_owned_directory(root)
    found: list[Path] = []
    for parent_rel in ALLOWED_PARENTS:
        parent = root / parent_rel
        if not parent.exists() and not parent.is_symlink():
            continue
        _require_owned_directory(parent)
        cache = parent / CACHE_NAME
        if not cache.exists() and not cache.is_symlink():
            continue
        _require_owned_directory(cache)
        for child in cache.iterdir():
            info = child.lstat()
            if (not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or child.is_symlink()
                    or child.suffix not in ALLOWED_EXTENSIONS
                    or info.st_size > MAX_CACHE_FILE_BYTES):
                raise HygieneBlocked("unexpected_cache_content")
            found.append(child)
    return found


def clean(root: Path, *, apply: bool = False) -> dict:
    selected = plan(root)
    if not apply:
        return {
            "status": "DRY_RUN", "eligible_python_cache_files": len(selected),
            "removed_files": 0, "other_projects_modified": False,
        }
    if root != CANONICAL_ROOT:
        raise HygieneBlocked("apply_requires_canonical_telegram_leads_root")
    # Recheck the complete set before doing any deletion and refuse stale or
    # symlinked entries. This script intentionally leaves empty dirs alone.
    for item in selected:
        if item.is_symlink() or not item.is_file():
            raise HygieneBlocked("cache_changed_before_removal")
    removed = 0
    for item in selected:
        # A compromised directory is never followed, even after the preflight.
        _require_owned_directory(item.parent)
        info = item.lstat()
        if (not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_size > MAX_CACHE_FILE_BYTES
                or item.suffix not in ALLOWED_EXTENSIONS):
            raise HygieneBlocked("cache_changed_before_removal")
        item.unlink()
        removed += 1
    return {
        "status": "APPLIED",
        "eligible_python_cache_files": len(selected),
        "removed_files": removed,
        "other_projects_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=CANONICAL_ROOT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-telegram-only", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.confirm_telegram_only:
        parser.error("--apply requires --confirm-telegram-only")
    if args.confirm_telegram_only and not args.apply:
        parser.error("--confirm-telegram-only requires --apply")
    try:
        result = clean(args.root, apply=args.apply)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (HygieneBlocked, OSError) as exc:
        code = str(exc) if isinstance(exc, HygieneBlocked) else "os_error"
        print(json.dumps({"status": "BLOCKED", "reason": code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
