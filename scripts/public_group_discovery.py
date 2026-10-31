#!/usr/bin/env python3
"""Find public Telegram groups by topic without enumerating or contacting people.

Uses the owner's existing, in-memory Telethon session. This tool reads public
group search results only. It never joins a group, lists its participants,
messages users, or adds anyone to the owner's group.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import stat
import tempfile

from telethon import errors
from telethon.tl.functions.contacts import SearchRequest

from telethon_sessions import DEFAULT_VAULT, inspect, make_memory_client

DEFAULT_CATALOG = Path("/var/lib/telegram-robot-leads/public-groups.json")
KEYWORDS_FILE = "discovery_keywords.txt"
GROUP_NAME = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
MAX_KEYWORDS = 6
MAX_RESULTS_PER_QUERY = 30
MAX_CATALOG_GROUPS = 2500
MAX_CATALOG_BYTES = 2 * 1024 * 1024

# Public group name searches, never participant access or verified geolocation.
REGIONAL_KEYWORDS = {
    "PT_ES": ("iptv portugal", "iptv espana", "iptv espanha"),
    "EU_OTHER": ("iptv france", "iptv germany", "iptv italia",
                 "iptv nederland", "iptv europe"),
}
REGIONAL_ACCOUNTS = {"PT_ES": 1, "EU_OTHER": 2}


class DiscoveryBlocked(RuntimeError):
    """A prerequisite or a Telegram protection prevented a safe discovery."""


def _private_keywords(vault: Path) -> list[str] | None:
    path = vault / KEYWORDS_FILE
    if path.is_symlink():
        raise DiscoveryBlocked("keywords_symlink_invalid")
    if not path.exists():
        return None
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 8192):
        raise DiscoveryBlocked("keywords_permissions_or_size_invalid")
    return path.read_text(encoding="utf-8").splitlines()


def select_keywords(vault: Path, target: str, supplied: list[str]) -> list[str]:
    """Use CLI keywords, a protected file or the existing IPTV project topic."""
    lines = supplied if supplied else _private_keywords(vault)
    if lines is None:
        # Only this project's documented IPTV identity has a safe default.
        if "iptv" not in target.casefold():
            raise DiscoveryBlocked("discovery_keywords_missing")
        lines = ["iptv portugal", "iptv"]
    keywords: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if not (3 <= len(value) <= 64) or not value.isprintable():
            raise DiscoveryBlocked("discovery_keyword_invalid")
        key = value.casefold()
        if key not in seen:
            keywords.append(value)
            seen.add(key)
        if len(keywords) > MAX_KEYWORDS:
            raise DiscoveryBlocked("discovery_keyword_limit")
    if not keywords:
        raise DiscoveryBlocked("discovery_keywords_empty")
    return keywords


def _validate_regional_account(config: dict, account_number: int,
                               region: str | None) -> None:
    if type(account_number) is not int or account_number not in (1, 2):
        raise DiscoveryBlocked("discovery_account_invalid")
    entries = config.get("entries")
    if not isinstance(entries, (list, tuple)) or len(entries) < account_number:
        raise DiscoveryBlocked("discovery_account_session_missing")
    if region is not None and REGIONAL_ACCOUNTS.get(region) != account_number:
        raise DiscoveryBlocked("discovery_region_account_mismatch")


def select_regional_keywords(vault: Path, target: str, region: str) -> list[str]:
    """Search terms indicate regional relevance, not a group's real location."""
    if region not in REGIONAL_KEYWORDS:
        raise DiscoveryBlocked("discovery_region_invalid")
    if "iptv" not in target.casefold():
        raise DiscoveryBlocked("discovery_region_niche_unverified")
    return select_keywords(vault, target, list(REGIONAL_KEYWORDS[region]))


def public_join_url(target: str) -> str:
    if not GROUP_NAME.fullmatch(target):
        raise DiscoveryBlocked("target_not_a_public_group_username")
    return "https://t.me/" + target[1:]


def select_public_groups(chats: list, target: str, keyword: str) -> list[dict]:
    """Inspect only the chats vector returned by Telegram; never its users."""
    found = []
    seen: set[str] = set()
    for chat in chats:
        if getattr(chat, "megagroup", False) is not True:
            continue
        if getattr(chat, "broadcast", False) is True:
            continue
        username = getattr(chat, "username", None)
        if not isinstance(username, str):
            continue
        handle = "@" + username.removeprefix("@")
        if not GROUP_NAME.fullmatch(handle):
            continue
        key = handle.casefold()
        if key == target.casefold() or key in seen:
            continue
        title = str(getattr(chat, "title", "")).replace("\n", " ").replace("\r", " ").strip()[:120]
        found.append({
            "username": handle,
            "title": title,
            "url": "https://t.me/" + handle[1:],
            "matched_keywords": [keyword],
        })
        seen.add(key)
    return found


def read_catalog(path: Path) -> dict:
    if path.is_symlink() or path.parent.is_symlink():
        raise DiscoveryBlocked("catalog_symlink_invalid")
    if not path.exists():
        return {"schema": 1, "groups": {}, "last_scan_at": None}
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_CATALOG_BYTES):
        raise DiscoveryBlocked("catalog_permissions_or_size_invalid")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise DiscoveryBlocked("catalog_unreadable") from exc
    if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("groups"), dict)
            or len(data["groups"]) > MAX_CATALOG_GROUPS):
        raise DiscoveryBlocked("catalog_invalid")
    return data


def write_catalog(path: Path, catalog: dict) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise DiscoveryBlocked("catalog_symlink_invalid")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise DiscoveryBlocked("catalog_directory_permissions_invalid")
    payload = json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2)
    if len(payload.encode("utf-8")) > MAX_CATALOG_BYTES:
        raise DiscoveryBlocked("catalog_size_limit")
    fd, tmp = tempfile.mkstemp(prefix=".public-groups-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def catalog_lock(path: Path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise DiscoveryBlocked("catalog_directory_permissions_invalid")
    lock = path.with_name(path.name + ".lock")
    if lock.is_symlink():
        raise DiscoveryBlocked("catalog_lock_symlink_invalid")
    if not hasattr(os, "O_NOFOLLOW"):
        raise DiscoveryBlocked("secure_lock_unavailable")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise DiscoveryBlocked("catalog_lock_permissions_invalid")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DiscoveryBlocked("another_discovery_running") from exc
        yield
    finally:
        os.close(fd)


def merge_results(catalog: dict, candidates: list[dict], stamp: str,
                  region: str | None = None) -> int:
    groups = catalog["groups"]
    new_count = 0
    for item in candidates:
        key = item["username"].casefold()
        prior = groups.get(key)
        if prior is None:
            if len(groups) >= MAX_CATALOG_GROUPS:
                continue
            prior = {"first_seen_at": stamp, "matched_keywords": []}
            new_count += 1
        seen_keywords = set(prior.get("matched_keywords", []))
        seen_keywords.update(item["matched_keywords"])
        record = {
            "username": item["username"],
            "title": item["title"],
            "url": item["url"],
            "matched_keywords": sorted(seen_keywords, key=str.casefold)[:MAX_KEYWORDS],
            "first_seen_at": prior["first_seen_at"],
            "last_seen_at": stamp,
        }
        earlier = prior.get("matched_regions", [])
        regional_tags = ({tag for tag in earlier if tag in REGIONAL_KEYWORDS}
                         if isinstance(earlier, list) else set())
        if region is not None:
            regional_tags.add(region)
        if regional_tags:
            record["matched_regions"] = sorted(regional_tags)
        groups[key] = record
    return new_count


async def discover_once(config: dict, keywords: list[str], catalog_path: Path = DEFAULT_CATALOG,
                        client_factory=None, delay_seconds: float = 3,
                        *, account_number: int = 1, region: str | None = None) -> dict:
    """Search public group names/titles; store no individual user information."""
    _validate_regional_account(config, account_number, region)
    target = config["group"]
    join_url = public_join_url(target)
    factory = client_factory or make_memory_client
    total_new = 0
    with catalog_lock(catalog_path):
        catalog = read_catalog(catalog_path)
        client = factory(config["entries"][account_number - 1], config)
        try:
            await asyncio.wait_for(client.connect(), timeout=25)
            if not await asyncio.wait_for(client.is_user_authorized(), timeout=20):
                raise DiscoveryBlocked("existing_account_not_authorized")
            for index, keyword in enumerate(keywords):
                try:
                    answer = await asyncio.wait_for(
                        client(SearchRequest(q=keyword, limit=MAX_RESULTS_PER_QUERY)),
                        timeout=30,
                    )
                except (errors.FloodWaitError, errors.PeerFloodError,
                        errors.UserRestrictedError) as exc:
                    raise DiscoveryBlocked("telegram_search_rate_or_account_restriction") from exc
                chats = getattr(answer, "chats", None)
                if not isinstance(chats, (list, tuple)):
                    raise DiscoveryBlocked("telegram_search_response_invalid")
                candidates = select_public_groups(chats, target, keyword)
                stamp = datetime.now(timezone.utc).isoformat()
                total_new += merge_results(catalog, candidates, stamp, region=region)
                catalog["last_scan_at"] = stamp
                write_catalog(catalog_path, catalog)
                if index + 1 < len(keywords) and delay_seconds:
                    await asyncio.sleep(delay_seconds)
        finally:
            if client.is_connected():
                await client.disconnect()
    return {
        "status": "PUBLIC_DISCOVERY_COMPLETE",
        "account_number": account_number,
        "region": region,
        "queries": len(keywords),
        "new_public_groups": total_new,
        "total_public_groups": len(catalog["groups"]),
        "catalog": str(catalog_path),
        "voluntary_join_url": join_url,
        "members_collected": 0,
        "users_contacted": 0,
        "members_added": 0,
    }



async def discover_daily(config: dict, vault: Path, catalog_path: Path = DEFAULT_CATALOG,
                         client_factory=None, delay_seconds: float = 3,
                         day: str | None = None, *,
                         account_number: int = 1, region: str | None = None) -> dict:
    """At most one discovery attempt per account per Lisbon calendar day.

    Persist each attempt before Telegram calls. A prior account-1 legacy scan
    counts as today's regional account-1 scan, preventing duplicate queries.
    """
    _validate_regional_account(config, account_number, region)
    keywords = (select_regional_keywords(vault, config["group"], region)
                if region is not None else
                select_keywords(vault, config["group"], []))
    stamp_day = day or datetime.now(ZoneInfo("Europe/Lisbon")).date().isoformat()
    with catalog_lock(catalog_path):
        catalog = read_catalog(catalog_path)
        if region is None:
            if catalog.get("last_attempt_day") == stamp_day:
                return {"status": "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
                        "queries": 0, "new_public_groups": 0}
            catalog["last_attempt_day"] = stamp_day
        else:
            attempts = catalog.get("regional_attempts", {})
            if not isinstance(attempts, dict):
                raise DiscoveryBlocked("discovery_regional_attempts_invalid")
            previous = attempts.get(str(account_number)) == stamp_day
            legacy = (account_number == 1
                      and catalog.get("last_attempt_day") == stamp_day)
            if previous or legacy:
                return {"status": "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
                        "account_number": account_number, "region": region,
                        "queries": 0, "new_public_groups": 0}
            attempts[str(account_number)] = stamp_day
            catalog["regional_attempts"] = attempts
            if account_number == 1:
                catalog["last_attempt_day"] = stamp_day
        write_catalog(catalog_path, catalog)
    return await discover_once(config, keywords, catalog_path,
                               client_factory=client_factory,
                               delay_seconds=delay_seconds,
                               account_number=account_number, region=region)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--once", action="store_true", help="Perform one public group search")
    choice.add_argument("--list", action="store_true", help="Show saved public groups offline")
    choice.add_argument("--preview", action="store_true", help="Check search topics without Telegram calls")
    parser.add_argument("--query", action="append", default=[], help="Optional public group search topic (repeatable)")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    args = parser.parse_args()
    try:
        if args.list:
            data = read_catalog(DEFAULT_CATALOG)
            print(json.dumps({"status": "OK", "last_scan_at": data["last_scan_at"],
                              "groups": sorted(data["groups"].values(), key=lambda g: g["username"].casefold())},
                             ensure_ascii=False))
            return 0
        config = inspect(args.vault)
        queries = select_keywords(args.vault, config["group"], args.query)
        if args.preview:
            print(json.dumps({"status": "READY_OFFLINE", "keywords": queries,
                              "voluntary_join_url": public_join_url(config["group"]),
                              "telegram_requests": 0}, ensure_ascii=False))
            return 0
        result = asyncio.run(discover_once(config, queries))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (DiscoveryBlocked, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc) or type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
