#!/usr/bin/env python3
"""Two-step, consent-only transfer between Telegram groups the operator administers.

Step 1: verify a short list of people who expressly requested a move AND are
currently members of one operator-managed source supergroup (read-only MTProto).
Step 2: with explicit operator confirmation, queue only verified people in
the *existing* approved_users.txt; the existing bounded runtime handles any
actual additions under Telegram rules. Neither step enumerates third-party
participant lists, sends messages, nor sends invitations.

This opt-in utility is not part of the running PM2 loop. It cannot run without
explicit group admin rights and operator-held consent records.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from zoneinfo import ZoneInfo
from typing import Any, Callable

from telethon import errors
from telethon.tl.functions.channels import GetParticipantRequest

from safe_runtime import (
    DEFAULT_APPROVED_USERS, USER_RE, load_approved_users,
)
from telethon_sessions import (
    DEFAULT_VAULT, GROUP_NAME, ProbeBlocked, inspect, make_memory_client,
)

CONSENT_FILENAME = "migration_optins.txt"
MAX_FILE_BYTES = 65536
MAX_CONSENT_ROWS = 100
MAX_PER_SOURCE = 10
MAX_QUEUE_FILE_BYTES = 1024 * 1024
REFERENCE_RE = re.compile(r"(?:dm|joinreq):[1-9][0-9]{0,18}\Z")
PUBLIC_KEY = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")


class TransferBlocked(RuntimeError):
    """A required authorization, consent or platform permission was absent."""


def _private_file(path: Path, vault: Path, size_limit: int) -> str:
    if path.parent != vault or path.is_symlink():
        raise TransferBlocked("private_file_path_invalid")
    try:
        info = path.lstat()
    except OSError as exc:
        raise TransferBlocked("private_file_missing") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > size_limit):
        raise TransferBlocked("private_file_permissions_or_size_invalid")
    if not hasattr(os, "O_NOFOLLOW"):
        raise TransferBlocked("secure_open_unavailable")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as input_file:
        return input_file.read(size_limit + 1)


def read_consents(vault: Path, source: str, *, today: date | None = None) -> list[dict]:
    """Load *declared* opt-ins. References are operator records, NOT proof alone."""
    if not GROUP_NAME.fullmatch(source):
        raise TransferBlocked("source_username_invalid")
    from telethon_sessions import _private_dir
    _private_dir(vault)
    raw = _private_file(vault / CONSENT_FILENAME, vault, MAX_FILE_BYTES)
    if len(raw.encode("utf-8")) > MAX_FILE_BYTES:
        raise TransferBlocked("consent_file_too_large")
    now = today or date.today()
    selected: list[dict] = []
    seen: set[str] = set()
    valid_rows = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        valid_rows += 1
        if valid_rows > MAX_CONSENT_ROWS:
            raise TransferBlocked("consent_file_record_limit")
        fields = [item.strip() for item in line.split("|")]
        if len(fields) != 5:
            raise TransferBlocked("consent_record_invalid")
        username, marker, group, on_date, reference = fields
        if (not USER_RE.fullmatch(username) or marker != "CONSENTED"
                or not GROUP_NAME.fullmatch(group)
                or not REFERENCE_RE.fullmatch(reference)):
            raise TransferBlocked("consent_record_invalid")
        try:
            when = date.fromisoformat(on_date)
        except ValueError as exc:
            raise TransferBlocked("consent_date_invalid") from exc
        if when > now or when < now - timedelta(days=90):
            raise TransferBlocked("consent_outside_valid_window")
        if group.casefold() != source.casefold():
            continue
        key = username.casefold()
        if key in seen:
            raise TransferBlocked("duplicate_consent_record")
        seen.add(key)
        selected.append({"username": username, "source": group,
                         "reference": reference, "date": when.isoformat()})
        if len(selected) > MAX_PER_SOURCE:
            raise TransferBlocked("too_many_optins_for_single_action")
    if not selected:
        raise TransferBlocked("no_explicit_optins_for_source")
    return selected


def _eligible_participant(result: Any, expected_id: int) -> bool:
    """Verify identity and normal membership; reject bots, admins and deleted."""
    member = getattr(result, "participant", None)
    if member is None or getattr(member, "user_id", None) != expected_id:
        return False
    if type(member).__name__ in {
        "ChannelParticipantAdmin", "ChannelParticipantCreator",
        "ChannelParticipantBanned", "ChannelParticipantLeft",
        "ChannelParticipantSelf",
    }:
        return False
    if getattr(member, "admin_rights", None) is not None:
        return False
    users = getattr(result, "users", None)
    if not isinstance(users, (list, tuple)):
        return False
    matches = [user for user in users if getattr(user, "id", None) == expected_id]
    return len(matches) == 1 and not (
        getattr(matches[0], "deleted", False)
        or getattr(matches[0], "bot", False)
    )


async def check_source_members(
    config: dict,
    source: str,
    consents: list[dict],
    *,
    client_factory: Callable | None = None,
) -> dict:
    """Query only consented usernames in an admin-managed supergroup.

    Does not enumerate a participant list. Stops on unknown Telegram failures.
    """
    if config.get("api_source") != "private_app_credentials":
        raise TransferBlocked("own_telegram_app_credentials_required")
    if not GROUP_NAME.fullmatch(source):
        raise TransferBlocked("source_username_invalid")
    if not GROUP_NAME.fullmatch(config.get("group", "")):
        raise TransferBlocked("target_group_invalid")
    if source.casefold() == config["group"].casefold():
        raise TransferBlocked("source_equals_destination")
    if not consents or len(consents) > MAX_PER_SOURCE:
        raise TransferBlocked("consent_batch_size_invalid")
    if any(record.get("source", "").casefold() != source.casefold()
           or not USER_RE.fullmatch(record.get("username", ""))
           for record in consents):
        raise TransferBlocked("consent_source_mismatch")

    client = (client_factory or make_memory_client)(config["entries"][0], config)
    eligible: list[str] = []
    excluded = 0
    checked = 0
    try:
        await asyncio.wait_for(client.connect(), timeout=25)
        if not await asyncio.wait_for(client.is_user_authorized(), timeout=20):
            raise TransferBlocked("existing_telegram_account_not_authorized")
        chat = await asyncio.wait_for(client.get_entity(source), timeout=20)
        if not getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False):
            raise TransferBlocked("source_not_a_supergroup")
        permissions = await asyncio.wait_for(
            client.get_permissions(chat, "me"), timeout=20
        )
        if not (getattr(permissions, "is_admin", False)
                or getattr(permissions, "is_creator", False)):
            raise TransferBlocked("source_admin_rights_missing")
        for record in consents:
            username = record["username"]
            try:
                user = await asyncio.wait_for(
                    client.get_input_entity(username), timeout=20
                )
                numeric_id = getattr(user, "user_id", None)
                if type(numeric_id) is not int or numeric_id <= 0:
                    excluded += 1
                    continue
                response = await asyncio.wait_for(
                    client(GetParticipantRequest(channel=chat, participant=user)),
                    timeout=20,
                )
                checked += 1
                if _eligible_participant(response, numeric_id):
                    eligible.append(username)
                else:
                    excluded += 1
            except (errors.UserNotParticipantError,
                    errors.UsernameInvalidError,
                    errors.UsernameNotOccupiedError):
                checked += 1
                excluded += 1
                continue
            # Unexpected errors, rate limits or restricted rights abort.
            # Never switch Telegram sessions to bypass a denial.
    finally:
        if client.is_connected():
            await client.disconnect()
    return {"status": "AUTHORIZED_SOURCE_VERIFIED",
            "checked": checked, "eligible": eligible, "excluded": excluded,
            "source_admin_verified": True, "telegram_mutations": 0}


def _queue_filename() -> str:
    name = os.environ.get("TELEGRAM_APPROVED_USERS", DEFAULT_APPROVED_USERS)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name) or name in {".", ".."}:
        raise TransferBlocked("approved_queue_filename_invalid")
    return name


def enqueue_verified_users(vault: Path, usernames: list[str], *, confirm: bool) -> dict:
    """Atomically write only consented candidates into the EXISTING runtime queue."""
    if not confirm:
        raise TransferBlocked("human_confirmation_required")
    from telethon_sessions import _private_dir
    _private_dir(vault)
    if len(usernames) > MAX_PER_SOURCE or not usernames:
        raise TransferBlocked("eligible_queue_size_invalid")
    if any(not USER_RE.fullmatch(name) for name in usernames):
        raise TransferBlocked("eligible_username_invalid")
    filename = _queue_filename()
    target = vault / filename
    lock = vault / ".migration-optin-queue.lock"
    if target.is_symlink() or lock.is_symlink():
        raise TransferBlocked("queue_symlink_invalid")
    if not hasattr(os, "O_NOFOLLOW"):
        raise TransferBlocked("secure_lock_unavailable")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise TransferBlocked("queue_lock_permissions_invalid")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TransferBlocked("another_queue_update_active") from exc
        existing = load_approved_users(vault)
        done = {name.casefold() for name in existing}
        added = []
        for username in usernames:
            if username.casefold() not in done:
                done.add(username.casefold())
                added.append(username)
        if not added:
            return {"status": "NO_NEW_OPTINS", "new_queued": 0,
                    "total_approved": len(existing), "telegram_mutations": 0}
        old = _private_file(target, vault, MAX_QUEUE_FILE_BYTES) if target.exists() else ""
        suffix = "" if not old or old.endswith("\n") else "\n"
        payload = old + suffix + "".join(f"{username}|CONSENTED\n" for username in added)
        if len(payload.encode("utf-8")) > MAX_QUEUE_FILE_BYTES:
            raise TransferBlocked("approved_queue_too_large")
        temp_fd, temp_name = tempfile.mkstemp(prefix=".migration-approved-", dir=str(vault))
        try:
            os.fchmod(temp_fd, 0o600)
            with os.fdopen(temp_fd, "w", encoding="utf-8") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return {"status": "OPTINS_QUEUED_FOR_EXISTING_RUNTIME",
                "new_queued": len(added), "total_approved": len(existing) + len(added),
                "telegram_mutations": 0, "members_added": 0}
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true",
                      help="Only check private consent metadata; never connect Telegram")
    mode.add_argument("--verify", action="store_true",
                      help="Read-only Telegram checks, no queue changes")
    mode.add_argument("--queue", action="store_true",
                      help="Verify source admins/membership and queue consented users")
    parser.add_argument("--source", required=True, metavar="@SOURCE_GROUP")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--confirm-consented-transfer", action="store_true")
    args = parser.parse_args()
    try:
        if args.queue and not args.confirm_consented_transfer:
            raise TransferBlocked("human_confirmation_required")
        if args.confirm_consented_transfer and not args.queue:
            raise TransferBlocked("confirmation_without_queue")
        if not GROUP_NAME.fullmatch(args.source):
            raise TransferBlocked("source_username_invalid")
        # Do not infer owner/admin rights from a public username.
        records = read_consents(args.vault, args.source)
        if args.preview:
            output = {"status": "CONSENT_RECORDS_DECLARED_NOT_INDEPENDENTLY_PROVEN",
                      "optin_records": len(records), "telegram_requests": 0}
        else:
            config = inspect(args.vault)
            results = asyncio.run(check_source_members(config, args.source, records))
            if args.queue:
                queued = enqueue_verified_users(
                    args.vault, results["eligible"], confirm=True
                ) if results["eligible"] else {
                    "status": "NO_ELIGIBLE_OPTINS", "new_queued": 0,
                    "telegram_mutations": 0
                }
                output = {**queued, "source_admin_verified": True,
                          "eligible": len(results["eligible"]),
                          "excluded": results["excluded"]}
            else:
                output = {"status": "MEMBERSHIP_VERIFIED_READ_ONLY",
                          "source_admin_verified": True,
                          "checked": results["checked"],
                          "eligible": len(results["eligible"]),
                          "excluded": results["excluded"],
                          "telegram_mutations": 0}
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0
    except (TransferBlocked, ProbeBlocked, OSError, ValueError, UnicodeError,
            errors.RPCError, asyncio.TimeoutError) as exc:
        reason = str(exc)
        safe = reason if re.fullmatch(r"[a-z0-9_]{1,90}", reason) else type(exc).__name__
        print(json.dumps({"status": "BLOCKED", "reason": safe}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
