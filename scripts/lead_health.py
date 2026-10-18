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

PROCESS_NAME = "TELEGRAM-IPTVPN"
SAFE_DEFAULTS = {
    "TARGET_GROUP": "@iptvpncode",
    "MAX_ADDS_PROJECT_PER_DAY": "70",
    "MIN_ADDS_PER_DAY": "45",
    "MAX_ADDS_PER_DAY": "80",
    "TELEGRAM_INVITES_ENABLED": "1",
    "SCRAPE_ENABLED": "1",
    "TELEGRAM_ACTIVE_MODE": "0",
}
NUMERIC_KEYS = {"MAX_ADDS_PROJECT_PER_DAY", "MIN_ADDS_PER_DAY", "MAX_ADDS_PER_DAY"}
BOOL_KEYS = {"TELEGRAM_INVITES_ENABLED", "SCRAPE_ENABLED", "TELEGRAM_ACTIVE_MODE"}
CREDENTIAL_KEYS = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "API_ID", "API_HASH", "TELEGRAM_GROWTH_BOT_TOKEN")


def read_env_names_and_values(path: Path) -> dict[str, str]:
    """Read env file for analysis; caller must print allowlisted fields only."""
    if not path.is_file():
        return {}
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
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
    raw = str(raw).strip()
    if key in NUMERIC_KEYS:
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 8:
            return "INVALID"
        return raw
    if key in BOOL_KEYS:
        return "true" if raw.lower() in {"1", "true", "on", "yes"} else "false" if raw.lower() in {"0", "false", "off", "no"} else "INVALID"
    if key == "TARGET_GROUP":
        return raw if re.fullmatch(r"@[A-Za-z0-9_]{3,32}|-?[0-9]{5,20}", raw) else "INVALID"
    return "REDACTED"


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
    override = str(pm2_env.get("DOTENV_OVERRIDE", "0")).strip().lower() in {"1", "true", "yes", "on"}
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
    config = {}
    for key, default in SAFE_DEFAULTS.items():
        if key in private_env and (override or key not in pm2_env):
            raw, source = private_env[key], ".env"
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
        "configuration_candidates": config,
        "credentials": {
            "telegram_api_id_configured": present_keys["TELEGRAM_API_ID"] or present_keys["API_ID"] or sensitive["telegram_api.json"]["present"],
            "telegram_api_hash_configured": present_keys["TELEGRAM_API_HASH"] or present_keys["API_HASH"] or sensitive["telegram_api.json"]["present"],
            "growth_bot_token_configured": present_keys["TELEGRAM_GROWTH_BOT_TOKEN"],
            "connectivity_verified": False,
        },
        "files": sensitive,
        "accounts": counts,
        "database": _db_summary(root / "users.db"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    pm2, error = read_pm2()
    print(json.dumps(inspect(args.root, pm2, error), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
