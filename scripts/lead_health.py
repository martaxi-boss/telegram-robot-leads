#!/usr/bin/env python3
"""Read-only, secret-redacted diagnostics for the existing Telegram Leads VPS.

Does not import main.py (which loads credentials), mutate DB state or connect to Telegram.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
from typing import Any

PROCESS_NAME = "telegram-robot-leads"
LEGACY_PROCESS_NAME = "TELEGRAM-IPTVPN"  # Detection only; never start or restart.
METRICS_PROCESS_NAME = "TELEGRAM-LEADS-METRICS"
SAFE_DEFAULTS = {
    "TARGET_GROUP": "@iptvpncode",
    "TELEGRAM_TZ": "Europe/Lisbon",
    "TELEGRAM_GROUP_ALLOWLIST": "group_allowlist.txt",
    "TELEGRAM_APPROVED_USERS": "approved_users.txt",
    "TELEGRAM_OPERATION_STATE": "/var/lib/telegram-robot-leads/operation-state.json",
}
CREDENTIAL_KEYS = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "API_ID", "API_HASH", "TELEGRAM_GROWTH_BOT_TOKEN")


def read_env_names_and_values(path: Path, *, owner_only: bool = False) -> dict[str, str]:
    """Parse an env file without exposing its contents.

    Explicit external credentials use owner_only=True: the full path must be
    canonical and non-symlinked, and its directory/file belong only to the
    effective process owner. O_NOFOLLOW and fstat guard the opened file.
    """
    path = Path(path)
    if owner_only:
        if not path.is_absolute() or ".." in path.parts:
            raise PermissionError("Explicit credentials path must be absolute")
        try:
            if path.resolve(strict=True) != path:
                raise PermissionError("Credentials path must not contain symlinks")
            parent = path.parent.lstat()
            if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) & 0o077):
                raise PermissionError("Credentials directory must be owner-only")
            if not hasattr(os, "O_NOFOLLOW"):
                raise PermissionError("Symlink-safe file opening unavailable")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(fd)
                if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.geteuid()
                        or stat.S_IMODE(opened.st_mode) & 0o077):
                    raise PermissionError("Credentials file must be owner-only")
                with os.fdopen(fd, "r", encoding="utf-8") as file:
                    fd = -1
                    raw = file.read(131073)
                if len(raw) > 131072:
                    raise ValueError("Credentials file exceeds safe limit")
            finally:
                if fd >= 0:
                    os.close(fd)
        except OSError as error:
            raise PermissionError("Credentials are missing or not owner-only") from error
    else:
        if not path.is_file():
            return {}
        raw = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)\s*$", line)
        if not match:
            continue
        key, raw = match.groups()
        value = raw.strip()
        if value.startswith(('"', "'")) and value.endswith(value[0]) and len(value) >= 2:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        fields[key] = value
    return fields


def file_evidence(path: Path) -> dict[str, Any]:
    try:
        st = path.stat()
    except (OSError, ValueError):
        return {"present": False}
    mode = stat.S_IMODE(st.st_mode)
    return {
        "present": True,
        "mode": oct(mode),
        "owner_only": (mode & 0o077) == 0,
    }


def read_pm2() -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = subprocess.run(
            ["pm2", "jlist"], capture_output=True, text=True, timeout=8, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], "PM2 unavailable or timed out"
    if result.returncode != 0:
        return [], "PM2 query failed"
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, list):
            raise ValueError("invalid PM2 response")
        return payload, None
    except (ValueError, TypeError):
        return [], "PM2 returned invalid JSON"


def _safe_value(key: str, raw: str) -> str:
    # Only the public destination identifier can be safely shown to the operator.
    raw = str(raw).strip()
    if key == "TARGET_GROUP":
        return raw if re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}|-?[0-9]{5,20}", raw) else "INVALID"
    return "CONFIGURED" if raw else "MISSING"


def _db_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False}
    outcome: dict[str, Any] = {"present": True, "mode": "read-only"}
    try:
        # mode=ro will never create a missing database or write to an existing one.
        db_uri = path.resolve().as_uri().replace("file://", "file:") + "?mode=ro"
        with closing(sqlite3.connect(db_uri, uri=True, timeout=2)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            outcome["known_tables"] = sorted(tables.intersection({"users", "adder_events", "adder_daily"}))
            if "users" in tables:
                outcome["candidate_count"] = int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            if "adder_daily" in tables:
                row = db.execute("SELECT MAX(day), COALESCE(SUM(adds_ok),0) FROM adder_daily WHERE day=(SELECT MAX(day) FROM adder_daily)").fetchone()
                outcome["last_accounting_day"] = row[0]
                outcome["last_accounting_additions"] = int(row[1])
    except (sqlite3.Error, OSError, ValueError):
        outcome["error"] = "database not readable in read-only mode"
    return outcome


def inspect(root: Path, pm2_records: list[dict[str, Any]], pm2_error: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    env_path = root / ".env"
    private_env = read_env_names_and_values(env_path)
    proc = next((p for p in pm2_records if p.get("name") == PROCESS_NAME), None)
    pm2_env = proc.get("pm2_env", {}) if isinstance(proc, dict) else {}
    if not isinstance(pm2_env, dict):
        pm2_env = {}
    runtime = {
        "found": bool(proc),
        "name": PROCESS_NAME,
        "status": str(pm2_env.get("status", "unknown")) if proc else "not_found",
        "restart_count": pm2_env.get("restart_time") if proc and isinstance(pm2_env.get("restart_time"), int) else None,
        "pid": proc.get("pid") if proc and isinstance(proc.get("pid"), int) else None,
        "note": "PM2 running is not proof of Telegram connectivity or successful joins",
    }
    if pm2_error:
        runtime["diagnostic"] = pm2_error
    legacy_proc = next((p for p in pm2_records if p.get("name") == LEGACY_PROCESS_NAME), None)
    legacy_env = legacy_proc.get("pm2_env", {}) if isinstance(legacy_proc, dict) else {}
    legacy_runtime = {
        "found": bool(legacy_proc),
        "status": str(legacy_env.get("status", "unknown")) if legacy_proc else "not_found",
        "note": "Historical process: never start or migrate it automatically",
    }
    metrics_proc = next((p for p in pm2_records if p.get("name") == METRICS_PROCESS_NAME), None)
    metrics_pm2 = metrics_proc.get("pm2_env", {}) if isinstance(metrics_proc, dict) else {}
    metrics_runtime = {
        "found": bool(metrics_proc),
        "name": METRICS_PROCESS_NAME,
        "status": str(metrics_pm2.get("status", "unknown")) if metrics_proc else "not_found",
        "note": "PM2 state does not verify Telegram join events",
    }
    config = {}
    for key, default in SAFE_DEFAULTS.items():
        # TARGET_GROUP is read by the canonical session vault loader.
        if key == "TARGET_GROUP":
            raw = private_env.get(key, default)
            source = ".env" if key in private_env else "source_default"
        elif key in pm2_env:
            raw, source = pm2_env[key], "pm2"
        elif key in private_env:
            raw, source = private_env[key], ".env"
        else:
            raw, source = default, "source_default"
        config[key] = {"value": _safe_value(key, raw), "source": source}
    session_files = list(root.glob("*.session"))
    sensitive = {name: file_evidence(root / name) for name in (".env", "accounts.json", "telegram_api.json", "users.db", "estado_bot.json", "telethon_adder.log")}
    counts = {"session_files": len(session_files), "session_files_owner_only": all(file_evidence(f).get("owner_only") is True for f in session_files)}
    accounts = root / "accounts.json"
    if accounts.is_file():
        try:
            parsed = json.loads(accounts.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                counts["accounts_configured"] = len(parsed)
            else:
                counts["accounts_configured"] = "unverified_format"
        except (OSError, ValueError):
            counts["accounts_configured"] = "invalid_json"
    # Do not output or persist any secret value. Credentials are only presence indicators.
    present_keys = {key: bool(str(private_env.get(key) or pm2_env.get(key) or "").strip()) for key in CREDENTIAL_KEYS}
    return {
        "project": "telegram-robot-leads",
        "source": "read-only local snapshot",
        "runtime": runtime,
        "legacy_runtime": legacy_runtime,
        "metrics_runtime": metrics_runtime,
        "configuration_candidates": config,
        "legacy_config_keys_present": sum(1 for key in private_env if (
            key.startswith("SCRAPE_") or key.startswith("MIN_ADDS_")
            or key.startswith("MAX_ADDS_")
            or key in {"TELEGRAM_INVITES_ENABLED", "TELEGRAM_ACTIVE_MODE"}
        )),
        "credentials": {
            "telegram_api_id_configured": present_keys["TELEGRAM_API_ID"] or present_keys["API_ID"] or sensitive["telegram_api.json"]["present"],
            "telegram_api_hash_configured": present_keys["TELEGRAM_API_HASH"] or present_keys["API_HASH"] or sensitive["telegram_api.json"]["present"],
            "growth_bot_token_configured": present_keys["TELEGRAM_GROWTH_BOT_TOKEN"],
            "connectivity_verified": False,
        },
        "files": sensitive,
        "accounts": counts,
        "legacy_database_read_only": _db_summary(root / "users.db"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--with-pm2", action="store_true",
                        help="Explicitly query PM2 (can start a daemon in this user's namespace)")
    parser.add_argument("--no-pm2", action="store_true",
                        help="Compatibility option; PM2 is skipped by default")
    args = parser.parse_args()
    if args.with_pm2 and args.no_pm2:
        parser.error("--with-pm2 and --no-pm2 are mutually exclusive")
    # A seemingly read-only 'pm2 jlist' can auto-start a PM2 daemon.
    # Never contact PM2 implicitly, especially from another service account.
    pm2, error = read_pm2() if args.with_pm2 else ([], "PM2 deliberately not queried")
    print(json.dumps(inspect(args.root, pm2, error), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
