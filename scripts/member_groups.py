#!/usr/bin/env python3
"""Verify memberships of the owner's TWO accounts in already discovered public groups.

Only reads the owner's own Telegram dialogs and public group metadata. Does not
enumerate other members, join groups, send messages, or add anyone. The account
membership is the evidence; a search result alone never means "joined".
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from zoneinfo import ZoneInfo

from public_group_discovery import DEFAULT_CATALOG, read_catalog

REGISTRY_PATH = Path("/var/lib/telegram-robot-leads/member-groups.json")
GROUP_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
MAX_DIALOGS = 400
MAX_REGISTRY_BYTES = 2 * 1024 * 1024
MAX_GROUPS_PER_ACCOUNT = 2500
LISBON = ZoneInfo("Europe/Lisbon")


class RegistryBlocked(RuntimeError):
    """Local file permissions or state cannot be trusted."""


def _private_parent(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink() or path.parent.is_symlink():
        raise RegistryBlocked("registry_path_invalid")
    info = path.parent.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise RegistryBlocked("registry_directory_permissions_invalid")


def _empty() -> dict:
    return {
        "schema": 1,
        "accounts": {
            "1": {"last_attempt_day": None, "groups": {}},
            "2": {"last_attempt_day": None, "groups": {}},
        },
    }


def read_registry(path: Path = REGISTRY_PATH) -> dict:
    _private_parent(path)
    if not path.exists():
        return _empty()
    if path.is_symlink():
        raise RegistryBlocked("registry_symlink_invalid")
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_size > MAX_REGISTRY_BYTES):
        raise RegistryBlocked("registry_permissions_or_size_invalid")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RegistryBlocked("registry_unreadable") from exc
    if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("accounts"), dict)
            or set(data["accounts"]) != {"1", "2"}):
        raise RegistryBlocked("registry_schema_invalid")
    for account in data["accounts"].values():
        if not isinstance(account, dict) or not isinstance(account.get("groups"), dict):
            raise RegistryBlocked("registry_accounts_invalid")
        if len(account["groups"]) > MAX_GROUPS_PER_ACCOUNT:
            raise RegistryBlocked("registry_group_limit")
        day = account.get("last_attempt_day")
        if day is not None:
            try:
                if (not isinstance(day, str) or len(day) != 10
                        or datetime.fromisoformat(day).date().isoformat() != day):
                    raise ValueError("invalid day")
            except ValueError as exc:
                raise RegistryBlocked("registry_day_invalid") from exc
        for handle, record in account["groups"].items():
            if (not isinstance(handle, str) or not GROUP_RE.fullmatch(handle)
                    or handle != handle.casefold() or not isinstance(record, dict)
                    or record.get("status") not in {"MEMBER_CONFIRMED", "NOT_RECONFIRMED"}
                    or type(record.get("group_id")) is not int
                    or record["group_id"] <= 0
                    or not isinstance(record.get("verified_at"), str)):
                raise RegistryBlocked("registry_group_invalid")
    return data


def save_registry(path: Path, data: dict) -> None:
    _private_parent(path)
    if path.is_symlink():
        raise RegistryBlocked("registry_symlink_invalid")
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
    if len(payload.encode("utf-8")) > MAX_REGISTRY_BYTES:
        raise RegistryBlocked("registry_size_limit")
    fd, tmp = tempfile.mkstemp(prefix=".member-groups-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _verified_groups(dialogs: list, catalog_groups: dict, target: str, day: str) -> dict:
    """Compare dialogs already joined by the owner against public group catalog."""
    result = {}
    discovered = set(catalog_groups)
    for dialog in dialogs:
        entity = getattr(dialog, "entity", None)
        if not entity or getattr(entity, "megagroup", False) is not True:
            continue
        if getattr(entity, "broadcast", False):
            continue
        username = getattr(entity, "username", None)
        if not isinstance(username, str):
            continue
        handle = ("@" + username.removeprefix("@")).casefold()
        group_id = getattr(entity, "id", None)
        if (not GROUP_RE.fullmatch(handle) or handle == target.casefold()
                or handle not in discovered or type(group_id) is not int
                or group_id <= 0):
            continue
        tags = catalog_groups[handle].get("matched_regions", [])
        tags = ([t for t in tags if t in ("PT_ES", "EU_OTHER")]
                if isinstance(tags, list) else [])
        result[handle] = {
            "group_id": group_id,
            "status": "MEMBER_CONFIRMED",
            "verified_at": day,
            "matched_search_regions": sorted(set(tags)),
        }
    return result


async def sync_one(config: dict, account_number: int, connector, *,
                   registry_path: Path = REGISTRY_PATH,
                   catalog_path: Path = DEFAULT_CATALOG,
                   day: str | None = None) -> dict:
    """At most one read-only membership inventory per account per Lisbon day."""
    if type(account_number) is not int or account_number not in (1, 2):
        raise RegistryBlocked("account_number_invalid")
    entries = config.get("entries")
    if not isinstance(entries, (list, tuple)) or len(entries) < account_number:
        raise RegistryBlocked("session_entry_missing")
    date = day or datetime.now(LISBON).date().isoformat()
    catalog = read_catalog(catalog_path)
    groups = catalog["groups"]
    registry = read_registry(registry_path)
    account = registry["accounts"][str(account_number)]
    if account["last_attempt_day"] == date:
        return {"status": "MEMBERSHIP_ALREADY_SCANNED_TODAY",
                "account": account_number,
                "confirmed": sum(x["status"] == "MEMBER_CONFIRMED"
                                 for x in account["groups"].values())}
    # Record attempt BEFORE network requests. No automatic retry after timeout.
    account["last_attempt_day"] = date
    save_registry(registry_path, registry)
    if not groups:
        return {"status": "NO_DISCOVERED_GROUPS", "account": account_number,
                "confirmed": 0}
    client = await connector(config, account_number)
    try:
        dialogs = await asyncio.wait_for(
            client.get_dialogs(limit=MAX_DIALOGS), timeout=65)
        if not isinstance(dialogs, (list, tuple)):
            raise RegistryBlocked("dialogs_response_invalid")
        observed = _verified_groups(dialogs, groups, config["group"], date)
        previous = account["groups"]
        # No absence claim: a missing dialog can be hidden by pagination,
        # username changes or access restrictions. Never automatically rejoin.
        for handle, record in previous.items():
            if handle not in observed:
                observed[handle] = {**record, "status": "NOT_RECONFIRMED"}
        if len(observed) > MAX_GROUPS_PER_ACCOUNT:
            raise RegistryBlocked("registry_group_limit")
        account["groups"] = observed
        save_registry(registry_path, registry)
        return {
            "status": ("MEMBERSHIP_PARTIAL_DIALOG_LIMIT"
                       if len(dialogs) >= MAX_DIALOGS
                       else "MEMBERSHIP_SCAN_COMPLETE"),
            "account": account_number,
            "confirmed": sum(x["status"] == "MEMBER_CONFIRMED"
                             for x in observed.values()),
            "not_reconfirmed": sum(x["status"] == "NOT_RECONFIRMED"
                                   for x in observed.values()),
            "telegram_requests": 1,
            "third_party_users_collected": 0,
            "members_added": 0,
        }
    finally:
        if client.is_connected():
            await client.disconnect()
