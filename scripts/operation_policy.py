#!/usr/bin/env python3
"""Durable fail-closed daily limits for the Telegram Robot Leads safe runtime."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MAX_GROUP_JOINS_PER_ACCOUNT_DAY = 1
MAX_GROUP_JOINS_PROJECT_DAY = 2
MAX_MEMBER_ADDS_PER_ACCOUNT_DAY = 10
MAX_MEMBER_ADDS_PROJECT_DAY = 20
MIN_INTERVAL_SECONDS = 10 * 60
DEFAULT_TZ = "Europe/Lisbon"


class PolicyBlocked(RuntimeError):
    pass


class PolicyDeferred(RuntimeError):
    pass


def _today(tz_name: str = DEFAULT_TZ) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")


def _new_account() -> dict:
    return {
        "group_joins": 0,
        "member_adds": 0,
        "last_action": 0,
        "blocked": False,
        "reason": None,
    }


def empty_state(tz_name: str = DEFAULT_TZ) -> dict:
    return {
        "day": _today(tz_name),
        "accounts": {"1": _new_account(), "2": _new_account()},
        "joined_groups": {},
        "approved_users_done": {},
        "pending_group_actions": {},
        "pending_member_actions": {},
    }


def load_state(path: Path, tz_name: str = DEFAULT_TZ) -> dict:
    """Treat malformed or ambiguous state as a hard stop, never as zero usage."""
    if path.is_symlink():
        raise PolicyBlocked("state_symlink_invalid")
    if not path.exists():
        return empty_state(tz_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PolicyBlocked("state_unreadable") from exc
    if not isinstance(data, dict):
        raise PolicyBlocked("state_invalid")
    for key in ("joined_groups", "approved_users_done",
                "pending_group_actions", "pending_member_actions"):
        if key not in data:
            data[key] = {}
        if not isinstance(data[key], dict):
            raise PolicyBlocked("state_mapping_invalid")
    accounts = data.get("accounts")
    if not isinstance(accounts, dict):
        raise PolicyBlocked("state_accounts_invalid")
    for key in ("1", "2"):
        account = accounts.get(key)
        if not isinstance(account, dict):
            raise PolicyBlocked("state_account_invalid")
        for field in ("group_joins", "member_adds", "last_action"):
            value = account.get(field)
            if type(value) not in (int, float) or value < 0:
                raise PolicyBlocked("state_account_invalid")
        if type(account.get("blocked")) is not bool:
            raise PolicyBlocked("state_account_invalid")
        if account.get("blocked") and not isinstance(account.get("reason"), str):
            raise PolicyBlocked("state_block_reason_invalid")
    if data.get("day") != _today(tz_name):
        # Keep pending remote outcomes and platform hard stops across midnight.
        previous = data
        data = empty_state(tz_name)
        for key in ("joined_groups", "approved_users_done",
                    "pending_group_actions", "pending_member_actions"):
            data[key] = previous[key]
        for key in ("1", "2"):
            prior = previous["accounts"][key]
            data["accounts"][key]["blocked"] = prior["blocked"]
            data["accounts"][key]["reason"] = prior.get("reason")
            data["accounts"][key]["last_action"] = prior["last_action"]
    return data

def save_state(path: Path, state: dict) -> None:
    if path.is_symlink():
        raise PolicyBlocked("state_symlink_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def project_total(state: dict, field: str) -> int:
    return sum(int(state["accounts"][key].get(field, 0)) for key in ("1", "2"))


def check_action(state: dict, account_number: int, action_type: str, now: float | None = None) -> None:
    key = str(account_number)
    if key not in ("1", "2"):
        raise PolicyBlocked("account_invalid")
    account = state["accounts"][key]
    if account.get("blocked"):
        raise PolicyBlocked(
            f"account_{account_number}_blocked:{account.get('reason') or 'unknown'}"
        )

    if action_type == "group_join":
        if int(account.get("group_joins", 0)) >= MAX_GROUP_JOINS_PER_ACCOUNT_DAY:
            raise PolicyDeferred(f"account_{account_number}_group_daily_limit")
        if project_total(state, "group_joins") >= MAX_GROUP_JOINS_PROJECT_DAY:
            raise PolicyDeferred("project_group_daily_limit")
    elif action_type == "member_add":
        if int(account.get("member_adds", 0)) >= MAX_MEMBER_ADDS_PER_ACCOUNT_DAY:
            raise PolicyDeferred(f"account_{account_number}_member_daily_limit")
        if project_total(state, "member_adds") >= MAX_MEMBER_ADDS_PROJECT_DAY:
            raise PolicyDeferred("project_member_daily_limit")
    else:
        raise PolicyBlocked("action_type_invalid")

    current = time.time() if now is None else now
    last = float(account.get("last_action") or 0)
    if last and current - last < MIN_INTERVAL_SECONDS:
        raise PolicyDeferred(f"account_{account_number}_interval")


def record_success(state: dict, account_number: int, action_type: str, now: float | None = None) -> None:
    account = state["accounts"][str(account_number)]
    if action_type == "group_join":
        account["group_joins"] = int(account.get("group_joins", 0)) + 1
    elif action_type == "member_add":
        account["member_adds"] = int(account.get("member_adds", 0)) + 1
    else:
        raise PolicyBlocked("action_type_invalid")
    account["last_action"] = int(time.time() if now is None else now)


def block_account(state: dict, account_number: int, reason: str) -> None:
    account = state["accounts"][str(account_number)]
    account["blocked"] = True
    account["reason"] = str(reason)[:160]
