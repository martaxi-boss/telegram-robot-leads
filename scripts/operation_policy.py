#!/usr/bin/env python3
"""Durable fail-closed daily limits for the Telegram Robot Leads safe runtime."""

from __future__ import annotations

import json
import math
import os
import re
import stat
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MAX_MEMBER_ADDS_PER_ACCOUNT_DAY = 10
MAX_MEMBER_ADDS_PROJECT_DAY = 20
MIN_INTERVAL_SECONDS = 10 * 60
MEMBER_ACTIVITY_START_HOUR = 8
MEMBER_ACTIVITY_END_HOUR = 22
ACCOUNT_TIME_OFFSETS_MINUTES = {1: 0, 2: 42}
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
        "join_request_approvals": 0,
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
        "approved_user_ids_done": {},
        "pending_member_ids": {},
        "pending_group_actions": {},
        "pending_member_actions": {},
        "pending_join_requests": {},
        "approved_join_requests_done": {},
        "owned_promotion": {},
        "join_request_last_scan": 0,
    }


def load_state(path: Path, tz_name: str = DEFAULT_TZ) -> dict:
    """Treat malformed or ambiguous state as a hard stop, never as zero usage."""
    if path.is_symlink():
        raise PolicyBlocked("state_symlink_invalid")
    if not path.exists():
        return empty_state(tz_name)
    # Never trust a publicly readable, oversized or replaced state journal.
    # Verify the opened inode (not only the pathname) to prevent symlink races.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or info.st_size > 8 * 1024 * 1024):
                raise PolicyBlocked("state_permissions_or_size_invalid")
            data = json.load(stream)
    except PolicyBlocked:
        raise
    except Exception as exc:
        raise PolicyBlocked("state_unreadable") from exc
    if not isinstance(data, dict):
        raise PolicyBlocked("state_invalid")
    for key in ("joined_groups", "approved_users_done", "approved_user_ids_done",
                "pending_group_actions", "pending_member_actions", "pending_member_ids",
                "pending_join_requests", "approved_join_requests_done", "owned_promotion"):
        if key not in data:
            data[key] = {}
        if not isinstance(data[key], dict):
            raise PolicyBlocked("state_mapping_invalid")
    # Old valid releases lack these fields; default them without resetting old usage.
    if "join_request_last_scan" not in data:
        data["join_request_last_scan"] = 0
    if (type(data["join_request_last_scan"]) is not int
            or data["join_request_last_scan"] < 0):
        raise PolicyBlocked("join_request_scan_invalid")
    accounts = data.get("accounts")
    if not isinstance(accounts, dict):
        raise PolicyBlocked("state_accounts_invalid")
    for key in ("1", "2"):
        account = accounts.get(key)
        if not isinstance(account, dict):
            raise PolicyBlocked("state_account_invalid")
        if "join_request_approvals" not in account:
            account["join_request_approvals"] = 0
        for field in ("group_joins", "member_adds", "join_request_approvals", "last_action"):
            value = account.get(field)
            if (type(value) is not int or value < 0) and not (field == "last_action" and type(value) is float and math.isfinite(value) and value >= 0):
                raise PolicyBlocked("state_account_invalid")
        if type(account.get("blocked")) is not bool:
            raise PolicyBlocked("state_account_invalid")
        if account.get("blocked") and not isinstance(account.get("reason"), str):
            raise PolicyBlocked("state_block_reason_invalid")
    # An invalid or future day must never reset today's accounting or a
    # pending remote outcome. Only well-formed past days may roll over.
    state_day = data.get("day")
    today = _today(tz_name)
    if (not isinstance(state_day, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", state_day)):
        raise PolicyBlocked("state_day_invalid")
    try:
        date.fromisoformat(state_day)
    except ValueError as exc:
        raise PolicyBlocked("state_day_invalid") from exc
    if state_day > today:
        raise PolicyBlocked("state_day_in_future")
    if state_day != today:
        # Keep pending remote outcomes and platform hard stops across midnight.
        previous = data
        data = empty_state(tz_name)
        for key in ("joined_groups", "approved_users_done", "approved_user_ids_done",
                    "pending_group_actions", "pending_member_actions", "pending_member_ids",
                    "pending_join_requests", "approved_join_requests_done", "owned_promotion"):
            data[key] = previous[key]
        data["join_request_last_scan"] = previous["join_request_last_scan"]
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


def member_time_budget(account_number: int, now: float | None = None) -> int:
    """Return how many member slots are available by this point in the day.

    The 14-hour window is divided evenly across the ten daily positions.
    Account 2 is offset by half a slot so both accounts are not due together.
    """
    if account_number not in (1, 2):
        raise PolicyBlocked("account_invalid")
    current = time.time() if now is None else now
    local = datetime.fromtimestamp(current, ZoneInfo(DEFAULT_TZ))
    start = local.replace(
        hour=MEMBER_ACTIVITY_START_HOUR, minute=0, second=0, microsecond=0
    )
    end = local.replace(
        hour=MEMBER_ACTIVITY_END_HOUR, minute=0, second=0, microsecond=0
    )
    if local < start:
        return 0
    if local >= end:
        return MAX_MEMBER_ADDS_PER_ACCOUNT_DAY
    window_seconds = int((end - start).total_seconds())
    slot_seconds = window_seconds / MAX_MEMBER_ADDS_PER_ACCOUNT_DAY
    offset_seconds = ACCOUNT_TIME_OFFSETS_MINUTES[account_number] * 60
    elapsed = (local - start).total_seconds() - offset_seconds
    if elapsed < 0:
        return 0
    return min(
        MAX_MEMBER_ADDS_PER_ACCOUNT_DAY,
        int(elapsed // slot_seconds) + 1,
    )


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
        # Telegram restrictions and spacing apply; no daily group quota.
        pass
    elif action_type in ("member_add", "join_request_approval"):
        # One shared activity budget: approving requested members must not
        # silently expand the already-approved 10/account and 20/project caps.
        member_count = (
            int(account.get("member_adds", 0))
            + int(account.get("join_request_approvals", 0))
        )
        if member_count >= MAX_MEMBER_ADDS_PER_ACCOUNT_DAY:
            raise PolicyDeferred(f"account_{account_number}_member_daily_limit")
        project_count = (
            project_total(state, "member_adds")
            + project_total(state, "join_request_approvals")
        )
        if project_count >= MAX_MEMBER_ADDS_PROJECT_DAY:
            raise PolicyDeferred("project_member_daily_limit")
    else:
        raise PolicyBlocked("action_type_invalid")

    current = time.time() if now is None else now
    if action_type in ("member_add", "join_request_approval"):
        local_hour = datetime.fromtimestamp(current, ZoneInfo(DEFAULT_TZ)).hour
        if not MEMBER_ACTIVITY_START_HOUR <= local_hour < MEMBER_ACTIVITY_END_HOUR:
            raise PolicyDeferred("member_activity_window_08_22_portugal")
        if (int(account.get("member_adds", 0))
                + int(account.get("join_request_approvals", 0))) >= member_time_budget(
            account_number, now=current
        ):
            raise PolicyDeferred(f"account_{account_number}_member_day_distribution")
    last = float(account.get("last_action") or 0)
    if last and current - last < MIN_INTERVAL_SECONDS:
        raise PolicyDeferred(f"account_{account_number}_interval")


def record_success(state: dict, account_number: int, action_type: str, now: float | None = None) -> None:
    account = state["accounts"][str(account_number)]
    if action_type == "group_join":
        account["group_joins"] = int(account.get("group_joins", 0)) + 1
    elif action_type == "member_add":
        account["member_adds"] = int(account.get("member_adds", 0)) + 1
    elif action_type == "join_request_approval":
        account["join_request_approvals"] = (
            int(account.get("join_request_approvals", 0)) + 1
        )
    else:
        raise PolicyBlocked("action_type_invalid")
    account["last_action"] = int(time.time() if now is None else now)


def block_account(state: dict, account_number: int, reason: str) -> None:
    account = state["accounts"][str(account_number)]
    account["blocked"] = True
    account["reason"] = str(reason)[:160]
