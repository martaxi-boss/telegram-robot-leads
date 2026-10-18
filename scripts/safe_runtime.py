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
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re

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


def _state_path() -> Path:
    return Path(
        os.environ.get("TELEGRAM_OPERATION_STATE", str(DEFAULT_STATE))
    ).expanduser()


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
        state["pending_member_actions"][canonical] = {"account": account_number}
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
            state["pending_member_actions"].pop(canonical, None)
            return "added"
        except errors.UserAlreadyParticipantError:
            state["approved_users_done"][canonical] = {
                "account": account_number,
                "status": "already_member",
            }
            state["pending_member_actions"].pop(canonical, None)
            return "already_member"
        except (errors.UserPrivacyRestrictedError, errors.UserChannelsTooMuchError) as exc:
            state["approved_users_done"][canonical] = {
                "account": account_number,
                "status": "not_addable",
                "reason": type(exc).__name__,
            }
            state["pending_member_actions"].pop(canonical, None)
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


async def run_once(vault: Path = DEFAULT_VAULT) -> dict:
    config = inspect(vault)
    if config["api_source"] != "private_app_credentials":
        raise ProbeBlocked("automatic_runtime_requires_private_app_credentials")

    groups = load_group_allowlist(vault)
    users = load_approved_users(vault)
    path = _state_path()
    state = load_state(path, os.environ.get("TELEGRAM_TZ", "Europe/Lisbon"))
    report = {"group_actions": [], "member_actions": [], "blocked": []}

    for group in groups:
        account = assigned_account(group)
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

    return report


async def loop(vault: Path, interval: int) -> None:
    while True:
        try:
            report = await run_once(vault)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        except Exception as exc:
            print(
                json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}),
                flush=True,
            )
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
