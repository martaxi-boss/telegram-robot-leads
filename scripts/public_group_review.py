#!/usr/bin/env python3
"""Review discovered public groups and explicitly schedule selected groups.

No Telegram API calls, member enumeration, automatic joins or messaging.
Approving a public group here only adds its username to the existing
operator-owned allowlist for the normal, bounded worker to process.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from public_group_discovery import DEFAULT_CATALOG, DiscoveryBlocked, read_catalog
from safe_runtime import DEFAULT_GROUP_ALLOWLIST, GROUP_RE, load_group_allowlist
from telethon_sessions import DEFAULT_VAULT, ProbeBlocked

MAX_FILE = 1024 * 1024


class ReviewBlocked(RuntimeError):
    """The selection needs operator action or the vault failed a safety check."""


def private_group_filename() -> str:
    value = os.environ.get("TELEGRAM_GROUP_ALLOWLIST", DEFAULT_GROUP_ALLOWLIST)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) or value in {".", ".."}:
        raise ReviewBlocked("operator_allowlist_name_invalid")
    return value


def validate_private_vault(vault: Path) -> None:
    if vault.is_symlink() or not vault.is_absolute() or ".." in vault.parts:
        raise ReviewBlocked("operator_vault_path_invalid")
    try:
        st = vault.stat()
    except OSError as exc:
        raise ReviewBlocked("operator_vault_unavailable") from exc
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) & 0o077):
        raise ReviewBlocked("operator_vault_permissions_invalid")


def public_groups(catalog_path: Path) -> list[dict]:
    catalog = read_catalog(catalog_path)
    groups = catalog["groups"]
    out: list[dict] = []
    for key, item in groups.items():
        if not isinstance(item, dict):
            raise ReviewBlocked("catalog_entry_invalid")
        username = item.get("username")
        if not isinstance(username, str) or not GROUP_RE.fullmatch(username):
            raise ReviewBlocked("catalog_entry_invalid")
        if key != username.casefold():
            raise ReviewBlocked("catalog_username_key_invalid")
        title = item.get("title")
        if not isinstance(title, str) or len(title) > 120:
            raise ReviewBlocked("catalog_title_invalid")
        labels = item.get("matched_keywords")
        if not isinstance(labels, list) or not all(
            isinstance(word, str) and len(word) <= 64 for word in labels
        ):
            raise ReviewBlocked("catalog_keywords_invalid")
        out.append({
            "username": username,
            "title": title,
            "public_url": "https://t.me/" + username.lstrip("@"),
            "topics": labels,
        })
    return sorted(out, key=lambda item: item["username"].casefold())


def approve_group(
    group: str,
    *,
    vault: Path = DEFAULT_VAULT,
    catalog_path: Path = DEFAULT_CATALOG,
    confirm: bool = False,
) -> dict:
    """Require explicit operator consent for this particular public group."""
    if not confirm:
        raise ReviewBlocked("explicit_operator_confirmation_required")
    if not isinstance(group, str):
        raise ReviewBlocked("group_username_invalid")
    username = group if group.startswith("@") else "@" + group
    if not GROUP_RE.fullmatch(username):
        raise ReviewBlocked("group_username_invalid")
    allowed = {item["username"].casefold(): item
               for item in public_groups(catalog_path)}
    if username.casefold() not in allowed:
        raise ReviewBlocked("group_not_in_verified_public_catalog")
    validate_private_vault(vault)
    filename = private_group_filename()
    allowlist = vault / filename
    lock = vault / ".public-group-review.lock"
    if allowlist.is_symlink() or lock.is_symlink():
        raise ReviewBlocked("operator_file_symlink_invalid")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ReviewBlocked("secure_lock_unavailable")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ReviewBlocked("operator_lock_permissions_invalid")
        fcntl.flock(fd, fcntl.LOCK_EX)
        # Load the same allowlist as the production worker before any writes.
        # The worker's validator fails closed on malformed existing records.
        existing = load_group_allowlist(vault)
        if username.casefold() in {name.casefold() for name in existing}:
            return {"status": "ALREADY_APPROVED", "group": username,
                    "approved_groups": len(existing),
                    "telegram_requests": 0, "group_joins": 0}
        if allowlist.exists():
            info = allowlist.stat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or info.st_size > MAX_FILE):
                raise ReviewBlocked("operator_file_permissions_invalid")
            old = allowlist.read_text(encoding="utf-8")
        else:
            old = ""
        addition = username + "\n"
        separator = "\n" if old and not old.endswith("\n") else ""
        data = old + separator + addition
        if len(data.encode("utf-8")) > MAX_FILE:
            raise ReviewBlocked("operator_file_too_large")
        temporary_fd, name = tempfile.mkstemp(prefix=".group-allowlist-", dir=str(vault))
        try:
            os.fchmod(temporary_fd, 0o600)
            with os.fdopen(temporary_fd, "w", encoding="utf-8") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, allowlist)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return {"status": "OPERATOR_GROUP_APPROVED",
                "group": allowed[username.casefold()]["username"],
                "approved_groups": len(existing) + 1,
                "telegram_requests": 0, "group_joins": 0,
                "note": "Queued for policy-limited processing, not joined yet"}
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="View found public groups")
    mode.add_argument("--approve", metavar="@GROUP", help="Choose exactly one found group")
    parser.add_argument("--confirm-operator-selection", action="store_true",
                        help="Allow only this selected group to enter the existing queue")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    try:
        if args.list:
            if args.confirm_operator_selection:
                raise ReviewBlocked("confirmation_without_selection")
            print(json.dumps({"status": "REVIEW_CANDIDATES",
                              "groups": public_groups(args.catalog)},
                             ensure_ascii=False, sort_keys=True))
        else:
            result = approve_group(
                args.approve, vault=args.vault, catalog_path=args.catalog,
                confirm=args.confirm_operator_selection)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ReviewBlocked, DiscoveryBlocked, ProbeBlocked, ValueError, OSError) as exc:
        # No secret values are intentionally included in these bounded codes.
        message = str(exc)
        code = message if re.fullmatch(r"[a-z0-9_]{1,90}", message) else "review_failed"
        print(json.dumps({"status": "BLOCKED", "reason": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
