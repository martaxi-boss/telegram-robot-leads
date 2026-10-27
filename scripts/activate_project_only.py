#!/usr/bin/env python3
"""Restart only the already-running canonical Telegram Robot Leads PM2 worker.

Requires a known existing PM2 daemon from the same Unix user; never runs
pm2 start, pm2 resurrect, pm2 save, pm2 delete, or global restarts.
Absent/unverified PM2 is a hard stop and must not be guessed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path("/opt/telegram-robot-leads")
PROCESS = "telegram-robot-leads"
SHA = re.compile(r"[0-9a-f]{40}\Z")


class ActivationBlocked(RuntimeError):
    pass


def _check_daemon_home(pm2_home: Path) -> int:
    if not pm2_home.is_absolute() or pm2_home.is_symlink():
        raise ActivationBlocked("pm2_home_not_canonical")
    if pm2_home.resolve() != pm2_home:
        raise ActivationBlocked("pm2_home_not_canonical")
    info = pm2_home.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise ActivationBlocked("pm2_home_not_owned")
    socket = pm2_home / "rpc.sock"
    if socket.is_symlink() or not socket.exists():
        raise ActivationBlocked("existing_pm2_socket_required")
    if not stat.S_ISSOCK(socket.lstat().st_mode):
        raise ActivationBlocked("pm2_socket_invalid")
    pidfile = pm2_home / "pm2.pid"
    if pidfile.is_symlink():
        raise ActivationBlocked("pm2_pid_symlink_invalid")
    try:
        pid = int(pidfile.read_text(encoding="ascii").strip())
        if pid <= 1:
            raise ValueError("invalid daemon pid")
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    except (ValueError, OSError) as exc:
        raise ActivationBlocked("pm2_daemon_not_verified") from exc
    if b"PM2" not in cmdline or str(pm2_home).encode() not in cmdline:
        raise ActivationBlocked("pm2_daemon_identity_mismatch")
    return pid


def _read_worker(pm2_home: Path, daemon_pid: int) -> dict:
    env = dict(os.environ, PM2_HOME=str(pm2_home))
    try:
        result = subprocess.run(
            ["pm2", "jlist"], capture_output=True, text=True,
            env=env, timeout=9, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ActivationBlocked("pm2_listing_unavailable") from exc
    if result.returncode != 0:
        raise ActivationBlocked("pm2_listing_failed")
    # A missing daemon must never be silently replaced with a new one.
    if _check_daemon_home(pm2_home) != daemon_pid:
        raise ActivationBlocked("pm2_daemon_changed")
    try:
        records = json.loads(result.stdout)
    except ValueError as exc:
        raise ActivationBlocked("pm2_listing_unreadable") from exc
    if not isinstance(records, list):
        raise ActivationBlocked("pm2_listing_unreadable")
    workers = [
        item for item in records
        if isinstance(item, dict) and item.get("name") == PROCESS
    ]
    if len(workers) != 1:
        raise ActivationBlocked("project_worker_missing_or_duplicate")
    worker = workers[0]
    meta = worker.get("pm2_env")
    if not isinstance(meta, dict):
        raise ActivationBlocked("project_worker_invalid")
    if (meta.get("pm_cwd") != str(ROOT)
            or meta.get("pm_exec_path") != str(ROOT / "main.py")):
        raise ActivationBlocked("project_worker_path_mismatch")
    return worker


def activate(pm2_home: Path, expected_sha: str, *, apply: bool = False) -> dict:
    if not SHA.fullmatch(expected_sha):
        raise ActivationBlocked("expected_sha_invalid")
    if ROOT.is_symlink() or ROOT.resolve() != ROOT:
        raise ActivationBlocked("root_invalid")
    marker = ROOT / ".verified-source-commit"
    if marker.is_symlink() or not marker.is_file():
        raise ActivationBlocked("installed_marker_invalid")
    if marker.read_text(encoding="ascii").strip() != expected_sha:
        raise ActivationBlocked("installed_commit_mismatch")
    daemon_pid = _check_daemon_home(pm2_home)
    _read_worker(pm2_home, daemon_pid)
    if not apply:
        return {
            "status": "READY_FOR_TARGETED_RESTART",
            "worker": PROCESS, "other_projects_modified": False,
        }
    env = dict(os.environ, PM2_HOME=str(pm2_home))
    # No environment update: keep the worker's previous credentials and
    # settings untouched. Only the ONE validated project process restarts.
    try:
        restarted = subprocess.run(
            ["pm2", "restart", PROCESS], capture_output=True, text=True,
            env=env, timeout=18, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ActivationBlocked("project_restart_not_confirmed") from exc
    if restarted.returncode != 0:
        raise ActivationBlocked("project_restart_failed")
    after = _read_worker(pm2_home, daemon_pid)
    if after["pm2_env"].get("status") != "online":
        raise ActivationBlocked("project_restart_not_online")
    return {
        "status": "PROJECT_WORKER_RESTARTED",
        "worker": PROCESS, "installed_sha": expected_sha,
        "other_projects_modified": False,
        "telegram_members_added_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pm2-home", type=Path, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-telegram-only", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.confirm_telegram_only:
        parser.error("--apply requires --confirm-telegram-only")
    try:
        print(json.dumps(activate(
            args.pm2_home, args.expected_source, apply=args.apply
        ), sort_keys=True))
        return 0
    except (ActivationBlocked, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, ActivationBlocked) else "local_io_error"
        print(json.dumps({"status": "BLOCKED", "reason": reason},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
