#!/usr/bin/env python3
"""Safe operator-controlled Telegram runtime for two existing Telethon sessions.

Allowed inputs:
- group_allowlist.txt: public groups explicitly approved by the operator.
- approved_users.txt: users explicitly approved/consented for addition to TARGET_GROUP.

The module does not discover groups, scrape members, enumerate third-party
participants, mimic human behaviour, or retry abuse/rate-limit signals.
"""

from __future__ import annotations

import argparse
import fcntl
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import time

from telethon import errors
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest

from operation_policy import (
    PolicyBlocked,
    PolicyDeferred,
    block_account,
    check_action,
    load_state,
    record_success,
    save_state,
)
from telethon_sessions import DEFAULT_VAULT, ProbeBlocked, inspect, make_memory_client

GROUP_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
USER_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
DEFAULT_STATE = Path("/var/lib/telegram-robot-leads/operation-state.json")
DEFAULT_GROUP_ALLOWLIST = "group_allowlist.txt"
DEFAULT_APPROVED_USERS = "approved_users.txt"
DEFAULT_EVENT_JOURNAL = Path("/var/lib/telegram-robot-leads/supervisor-events.jsonl")


def _private_operator_file(path: Path, vault: Path, required: bool = False) -> list[str]:
    if path.parent != vault or path.is_symlink():
        raise ProbeBlocked("operator_file_path_invalid")
    if not path.exists():
        if required:
            raise ProbeBlocked("operator_file_missing")
        return []
    st = path.stat()
    if not path.is_file() or st.st_uid != os.geteuid() or (st.st_mode & 0o077):
        raise ProbeBlocked("operator_file_permissions_invalid")
    if st.st_size > 1024 * 1024:
        raise ProbeBlocked("operator_file_too_large")
    return path.read_text(encoding="utf-8").splitlines()


def load_group_allowlist(vault: Path) -> list[str]:
    configured = os.environ.get("TELEGRAM_GROUP_ALLOWLIST", DEFAULT_GROUP_ALLOWLIST)
    if "/" in configured or "\\" in configured:
        raise ProbeBlocked("group_allowlist_filename_invalid")
    lines = _private_operator_file(vault / configured, vault)
    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if not value.startswith("@"):
            value = "@" + value
        if not GROUP_RE.fullmatch(value):
            raise ProbeBlocked("group_allowlist_entry_invalid")
        canonical = value.lower()
        if canonical not in seen:
            seen.add(canonical)
            out.append(value)
    return out


def load_approved_users(vault: Path) -> list[str]:
    configured = os.environ.get("TELEGRAM_APPROVED_USERS", DEFAULT_APPROVED_USERS)
    if "/" in configured or "\\" in configured:
        raise ProbeBlocked("approved_users_filename_invalid")
    lines = _private_operator_file(vault / configured, vault)
    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        parts = [piece.strip() for piece in value.split("|")]
        if len(parts) != 2 or parts[1].upper() not in {"APPROVED", "CONSENTED"}:
            raise ProbeBlocked("approved_user_requires_explicit_marker")
        username = parts[0]
        if not username.startswith("@"):
            username = "@" + username
        if not USER_RE.fullmatch(username):
            raise ProbeBlocked("approved_user_invalid")
        canonical = username.lower()
        if canonical not in seen:
            seen.add(canonical)
            out.append(username)
    return out


def assigned_account(value: str) -> int:
    return (hashlib.sha256(value.lower().encode("utf-8")).digest()[0] % 2) + 1


def assigned_group_account(state: dict, group: str) -> int:
    """Allocate a new group to the account with spare daily join capacity.

    Preserve historical assignments for groups already joined or pending:
    rebalancing must never retry an ambiguous Telegram-side operation.
    """
    canonical = group.lower()
    for key in ("joined_groups", "pending_group_actions"):
        record = state.get(key, {}).get(canonical)
        if isinstance(record, dict) and record.get("account") in (1, 2):
            return record["account"]
    counts = [
        int(state["accounts"][str(number)]["group_joins"])
        for number in (1, 2)
    ]
    if counts[0] < counts[1]:
        return 1
    if counts[1] < counts[0]:
        return 2
    return assigned_account(group)


def _state_path() -> Path:
    return Path(
        os.environ.get("TELEGRAM_OPERATION_STATE", str(DEFAULT_STATE))
    ).expanduser()


def _event_journal_path() -> Path:
    return Path(
        os.environ.get("TELEGRAM_EVENT_JOURNAL", str(DEFAULT_EVENT_JOURNAL))
    ).expanduser()


def append_supervisor_event(event: dict) -> None:
    """Append one private, non-secret operational event for an external supervisor."""
    path = _event_journal_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise PolicyBlocked("event_journal_symlink_invalid")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "ts": int(time.time()),
        "event": event,
    }
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.geteuid() or (st.st_mode & 0o077):
            raise PolicyBlocked("event_journal_permissions_invalid")
        with os.fdopen(fd, "a", encoding="utf-8", closefd=False) as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


async def _connected_client(config: dict, account_number: int):
    client = make_memory_client(config["entries"][account_number - 1], config)
    await asyncio.wait_for(client.connect(), timeout=25)
    if not await asyncio.wait_for(client.is_user_authorized(), timeout=20):
        await client.disconnect()
        raise ProbeBlocked(f"account_{account_number}_not_authorized")
    return client


def _is_hard_stop(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (errors.FloodWaitError, errors.PeerFloodError, errors.UserRestrictedError),
    )


async def _join_one(
    config: dict, state: dict, group: str, account_number: int
) -> str:
    canonical = group.lower()
    if canonical in state["joined_groups"]:
        return "already_recorded"
    if canonical in state["pending_group_actions"]:
        raise PolicyBlocked("group_action_outcome_unknown_manual_reconciliation_required")
    check_action(state, account_number, "group_join")
    client = await _connected_client(config, account_number)
    try:
        entity = await asyncio.wait_for(client.get_entity(group), timeout=20)
        # Persist BEFORE contacting Telegram. A timeout after submission has
        # an unknowable remote outcome and must never trigger automatic replay.
        state["pending_group_actions"][canonical] = {"account": account_number}
        save_state(_state_path(), state)
        try:
            await asyncio.wait_for(client(JoinChannelRequest(entity)), timeout=25)
            record_success(state, account_number, "group_join")
            state["joined_groups"][canonical] = {
                "account": account_number,
                "status": "joined",
            }
            state["pending_group_actions"].pop(canonical, None)
            return "joined"
        except errors.UserAlreadyParticipantError:
            state["joined_groups"][canonical] = {
                "account": account_number,
                "status": "already_member",
            }
            state["pending_group_actions"].pop(canonical, None)
            return "already_member"
    except Exception as exc:
        if _is_hard_stop(exc):
            reason = type(exc).__name__
            if isinstance(exc, errors.FloodWaitError):
                reason += f":{exc.seconds}s"
            block_account(state, account_number, reason)
        raise
    finally:
        if client.is_connected():
            await client.disconnect()


async def _add_one(
    config: dict, state: dict, username: str, account_number: int
) -> str:
    canonical = username.lower()
    if canonical in state["approved_users_done"]:
        return "already_recorded"
    if canonical in state["pending_member_actions"]:
        raise PolicyBlocked("member_action_outcome_unknown_manual_reconciliation_required")
    check_action(state, account_number, "member_add")
    client = await _connected_client(config, account_number)
    try:
        target = await asyncio.wait_for(client.get_entity(config["group"]), timeout=20)
        user = await asyncio.wait_for(client.get_input_entity(username), timeout=20)
        numeric_id = getattr(user, "user_id", None)
        if type(numeric_id) is not int or numeric_id <= 0:
            raise ProbeBlocked("member_stable_identity_unavailable")
        stable_id = str(numeric_id)
        if stable_id in state["approved_user_ids_done"]:
            state["approved_users_done"][canonical] = {
                "account": account_number,
                "status": "already_recorded_identity",
            }
            return "already_recorded_identity"
        # Old ambiguous attempts without IDs cannot be deduplicated safely.
        if any(
            not isinstance(entry, dict) or type(entry.get("user_id")) is not int
            for entry in state["pending_member_actions"].values()
        ):
            raise PolicyBlocked("legacy_pending_member_identity_needs_review")
        if stable_id in state["pending_member_ids"]:
            raise PolicyBlocked("member_identity_outcome_unknown_manual_reconciliation_required")
        state["pending_member_actions"][canonical] = {
            "account": account_number, "user_id": numeric_id
        }
        state["pending_member_ids"][stable_id] = {
            "account": account_number, "username": canonical
        }
        save_state(_state_path(), state)
        try:
            await asyncio.wait_for(
                client(InviteToChannelRequest(target, [user])), timeout=25
            )
            record_success(state, account_number, "member_add")
            state["approved_users_done"][canonical] = {
                "account": account_number,
                "status": "added",
            }
            state["approved_user_ids_done"][stable_id] = {
                "account": account_number,
                "status": "added",
            }
            state["pending_member_actions"].pop(canonical, None)
            state["pending_member_ids"].pop(stable_id, None)
            return "added"
        except errors.UserAlreadyParticipantError:
            state["approved_users_done"][canonical] = {
                "account": account_number,
                "status": "already_member",
            }
            state["approved_user_ids_done"][stable_id] = {
                "account": account_number,
                "status": "already_member",
            }
            state["pending_member_actions"].pop(canonical, None)
            state["pending_member_ids"].pop(stable_id, None)
            return "already_member"
        except (errors.UserPrivacyRestrictedError, errors.UserChannelsTooMuchError) as exc:
            state["approved_users_done"][canonical] = {
                "account": account_number,
                "status": "not_addable",
                "reason": type(exc).__name__,
            }
            state["approved_user_ids_done"][stable_id] = {
                "account": account_number,
                "status": "not_addable",
            }
            state["pending_member_actions"].pop(canonical, None)
            state["pending_member_ids"].pop(stable_id, None)
            return "not_addable"
    except Exception as exc:
        if _is_hard_stop(exc):
            reason = type(exc).__name__
            if isinstance(exc, errors.FloodWaitError):
                reason += f":{exc.seconds}s"
            block_account(state, account_number, reason)
        raise
    finally:
        if client.is_connected():
            await client.disconnect()


async def _run_once_unlocked(vault: Path = DEFAULT_VAULT) -> dict:
    config = inspect(vault)

    groups = load_group_allowlist(vault)
    users = load_approved_users(vault)
    path = _state_path()
    state = load_state(path, os.environ.get("TELEGRAM_TZ", "Europe/Lisbon"))
    report = {"group_actions": [], "member_actions": [], "blocked": []}

    for group in groups:
        account = assigned_group_account(state, group)
        try:
            status = await _join_one(config, state, group, account)
            report["group_actions"].append(
                {"group": group, "account": account, "status": status}
            )
            save_state(path, state)
        except PolicyDeferred as exc:
            report["blocked"].append(
                {"account": account, "scope": "group", "reason": str(exc)}
            )
        except (PolicyBlocked, ProbeBlocked) as exc:
            report["blocked"].append(
                {"account": account, "scope": "group", "reason": str(exc)}
            )
        except Exception as exc:
            report["blocked"].append(
                {"account": account, "scope": "group", "reason": type(exc).__name__}
            )
            save_state(path, state)

    for username in users:
        account = assigned_account(username)
        try:
            status = await _add_one(config, state, username, account)
            report["member_actions"].append(
                {"user": username, "account": account, "status": status}
            )
            save_state(path, state)
        except PolicyDeferred as exc:
            report["blocked"].append(
                {"account": account, "scope": "member", "reason": str(exc)}
            )
        except (PolicyBlocked, ProbeBlocked) as exc:
            report["blocked"].append(
                {"account": account, "scope": "member", "reason": str(exc)}
            )
        except Exception as exc:
            report["blocked"].append(
                {"account": account, "scope": "member", "reason": type(exc).__name__}
            )
            save_state(path, state)

    append_supervisor_event({
        "kind": "cycle",
        "api_source": config["api_source"],
        "group_actions": report["group_actions"],
        "member_actions": report["member_actions"],
        "blocked": report["blocked"],
    })
    return report


async def run_once(vault: Path = DEFAULT_VAULT) -> dict:
    """Serialize the entire read/check/API/write cycle across all local workers.

    Never wait behind another active worker: a duplicate runtime must fail
    closed rather than queue Telegram side effects for a later replay.
    """
    state_path = _state_path()
    if state_path.is_symlink() or state_path.parent.is_symlink():
        raise PolicyBlocked("state_path_symlink_invalid")
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = state_path.with_name(state_path.name + ".lock")
    if lock_path.is_symlink():
        raise PolicyBlocked("state_lock_symlink_invalid")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_uid != os.geteuid():
            raise PolicyBlocked("state_lock_owner_invalid")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PolicyBlocked("another_runtime_active") from exc
        return await _run_once_unlocked(vault)
    finally:
        os.close(fd)


async def loop(vault: Path, interval: int) -> None:
    while True:
        try:
            report = await run_once(vault)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        except Exception as exc:
            blocked = {"status": "BLOCKED", "reason": type(exc).__name__}
            try:
                append_supervisor_event({"kind": "runtime_blocked", **blocked})
            except Exception:
                pass
            print(json.dumps(blocked), flush=True)
        await asyncio.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()

    if args.once == args.loop:
        parser.error("choose exactly one of --once or --loop")
    if args.interval < 30:
        parser.error("--interval must be at least 30 seconds")

    try:
        if args.once:
            print(
                json.dumps(
                    asyncio.run(run_once(args.vault)),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        asyncio.run(loop(args.vault, args.interval))
        return 0
    except (
        ProbeBlocked,
        PolicyBlocked,
        OSError,
        ValueError,
        TypeError,
        PermissionError,
        json.JSONDecodeError,
    ) as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "reason": str(exc) or type(exc).__name__}
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
