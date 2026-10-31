#!/usr/bin/env python3
"""Safe operator-controlled Telegram runtime for two existing Telethon sessions.

Allowed inputs:
- group_allowlist.txt: public groups explicitly approved by the operator.
- approved_users.txt: users explicitly approved/consented for addition to TARGET_GROUP.

Optional daily public group *discovery* uses Telegram public search only.
It never collects participants or auto-enrolls anyone. Group joins and
direct additions remain limited to explicitly authorized entries.
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
from public_group_discovery import DiscoveryBlocked, discover_daily, read_catalog, DEFAULT_CATALOG
from member_groups import RegistryBlocked, read_registry, sync_one
from organic_growth import (
    approve_pending_join_request,
    promote_owned_channel,
    read_model,
    select_intake_account,
)

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


def group_action_key(account_number: int, group: str) -> str:
    """Separate membership histories for the owner's two accounts."""
    if account_number not in (1, 2) or not GROUP_RE.fullmatch(group):
        raise PolicyBlocked("invalid_group_or_account")
    return f"{account_number}:{group.casefold()}"


def group_record(state: dict, field: str, account_number: int, group: str):
    """Read account-scoped and legacy records, never the other account's."""
    scoped = state[field].get(group_action_key(account_number, group))
    if scoped is not None:
        return scoped
    legacy = state[field].get(group.casefold())
    if isinstance(legacy, dict) and legacy.get("account") == account_number:
        return legacy
    return None


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
    try:
        await asyncio.wait_for(client.connect(), timeout=25)
        if not await asyncio.wait_for(client.is_user_authorized(), timeout=20):
            raise ProbeBlocked(f"account_{account_number}_not_authorized")
        return client
    except BaseException:
        # Even connection and authorization timeouts can leave an open
        # Telethon transport. Avoid reusing half-open memory sessions.
        try:
            await asyncio.wait_for(client.disconnect(), timeout=10)
        except Exception:
            pass
        raise


def _is_hard_stop(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (errors.FloodWaitError, errors.PeerFloodError, errors.UserRestrictedError),
    )


async def _join_one(
    config: dict, state: dict, group: str, account_number: int
) -> str:
    canonical = group.casefold()
    key = group_action_key(account_number, canonical)
    if group_record(state, "joined_groups", account_number, canonical) is not None:
        return "already_recorded"
    if group_record(state, "pending_group_actions", account_number, canonical) is not None:
        raise PolicyBlocked("group_action_outcome_unknown_manual_reconciliation_required")
    check_action(state, account_number, "group_join")
    client = await _connected_client(config, account_number)
    try:
        entity = await asyncio.wait_for(client.get_entity(group), timeout=20)
        # Persist BEFORE contacting Telegram. A timeout after submission has
        # an unknowable remote outcome and must never trigger automatic replay.
        state["pending_group_actions"][key] = {"account": account_number}
        save_state(_state_path(), state)
        try:
            await asyncio.wait_for(client(JoinChannelRequest(entity)), timeout=25)
            record_success(state, account_number, "group_join")
            state["joined_groups"][key] = {
                "account": account_number,
                "status": "joined",
            }
            state["pending_group_actions"].pop(key, None)
            return "joined"
        except errors.UserAlreadyParticipantError:
            state["joined_groups"][key] = {
                "account": account_number,
                "status": "already_member",
            }
            state["pending_group_actions"].pop(key, None)
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


def _record_not_addable(
    state: dict, username: str, user_id: str, account_number: int, reason: str
) -> str:
    """Record a Telegram-confirmed denial; never retry it or count a success."""
    state["approved_users_done"][username] = {
        "account": account_number,
        "status": "not_addable",
        "reason": reason,
    }
    state["approved_user_ids_done"][user_id] = {
        "account": account_number, "status": "not_addable"
    }
    state["pending_member_actions"].pop(username, None)
    state["pending_member_ids"].pop(user_id, None)
    return "not_addable"


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
        # The two authorised intake paths share a permanent identity history.
        # A person approved through a join request must never be directly
        # added again, including after departure or username change.
        if (stable_id in state["approved_user_ids_done"]
                or stable_id in state["approved_join_requests_done"]):
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
            outcome = await asyncio.wait_for(
                client(InviteToChannelRequest(target, [user])), timeout=25
            )
            # Telegram can return 200 OK while *not* adding the person.
            # messages.InvitedUsers.missing_invitees explicitly lists those
            # that could not be invited (e.g. due to privacy settings).
            # We only request one approved user at a time.
            missing = getattr(outcome, "missing_invitees", None)
            if not isinstance(missing, (list, tuple)):
                # An older/unrecognised response cannot prove success.
                # Keep the pre-request pending record for manual review.
                raise PolicyBlocked("invite_result_unverified_manual_reconciliation_required")
            if missing:
                if (len(missing) != 1
                        or type(getattr(missing[0], "user_id", None)) is not int
                        or missing[0].user_id != numeric_id):
                    raise PolicyBlocked("invite_result_identity_mismatch_manual_reconciliation_required")
                return _record_not_addable(
                    state, canonical, stable_id, account_number,
                    "TelegramMissingInvitee",
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
        except (
            errors.UserPrivacyRestrictedError,
            errors.UserChannelsTooMuchError,
            errors.UserNotMutualContactError,
        ) as exc:
            return _record_not_addable(
                state, canonical, stable_id, account_number, type(exc).__name__
            )
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
    model = read_model(vault, config.get("group", ""))

    discovery_enabled = os.environ.get(
        "TELEGRAM_PUBLIC_DISCOVERY_ENABLED", "0"
    ).lower() in {"1", "true", "yes", "on"}
    regional_enabled = os.environ.get(
        "TELEGRAM_REGIONAL_PUBLIC_DISCOVERY_ENABLED", "0"
    ).lower() in {"1", "true", "yes", "on"}
    if discovery_enabled and regional_enabled:
        # Account 1 handles PT/ES, account 2 the remaining European search
        # terms. This searches PUBLIC GROUP METADATA only; no member listings,
        # joins, messages, or additions are inferred from search results.
        regional = {}
        for account_number, region in ((1, "PT_ES"), (2, "EU_OTHER")):
            if state["accounts"][str(account_number)]["blocked"]:
                regional[str(account_number)] = {
                    "status": "BLOCKED", "region": region,
                    "reason": "account_hard_stop",
                }
                continue
            try:
                regional[str(account_number)] = await discover_daily(
                    config, vault, account_number=account_number, region=region,
                )
            except DiscoveryBlocked as exc:
                reason = str(exc)
                regional[str(account_number)] = {
                    "status": "BLOCKED", "region": region, "reason": reason,
                }
                if reason == "telegram_search_rate_or_account_restriction":
                    block_account(state, account_number, reason)
                    save_state(path, state)
            except Exception as exc:
                regional[str(account_number)] = {
                    "status": "ERROR", "region": region,
                    "reason": type(exc).__name__,
                }
        statuses = [item["status"] for item in regional.values()]
        if "PUBLIC_DISCOVERY_COMPLETE" in statuses:
            combined_status = "PUBLIC_DISCOVERY_COMPLETE"
        elif all(value == "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY"
                 for value in statuses):
            combined_status = "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY"
        else:
            combined_status = "REGIONAL_DISCOVERY_PARTIAL"
        report["public_discovery"] = {
            "status": combined_status,
            "regional_accounts": regional,
            "new_public_groups": sum(
                int(item.get("new_public_groups", 0))
                for item in regional.values()
            ),
        }
    elif discovery_enabled and state["accounts"]["1"]["blocked"]:
        # Discovery uses account 1. A durable Telegram hard stop applies to
        # searches too, including on later days and after worker restarts.
        report["public_discovery"] = {
            "status": "BLOCKED",
            "reason": "account_1_hard_stop",
        }
    elif discovery_enabled:
        try:
            report["public_discovery"] = await discover_daily(config, vault)
        except DiscoveryBlocked as exc:
            reason = str(exc)
            report["public_discovery"] = {"status": "BLOCKED", "reason": reason}
            if reason == "telegram_search_rate_or_account_restriction":
                # This is a real Telegram hard-stop for account 1, not a
                # configuration inconvenience to retry using account 2.
                block_account(state, 1, reason)
                save_state(path, state)
        except Exception as exc:
            # Discovery errors must remain visible without blocking unrelated
            # authorized work or divulging Telegram credentials in logs.
            report["public_discovery"] = {
                "status": "ERROR", "reason": type(exc).__name__
            }

    # Membership inventory is read-only and checks ONLY the owner's dialogs
    # against already discovered public groups; it never lists participants.
    report["group_memberships"] = {"status": "NOT_ENABLED"}
    if discovery_enabled:
        region_results = {}
        for account_number in (1, 2):
            label = str(account_number)
            if state["accounts"][label]["blocked"]:
                region_results[label] = {"status": "BLOCKED", "reason": "account_hard_stop"}
                continue
            try:
                outcome = await sync_one(config, account_number, _connected_client)
                region_results[label] = outcome
                # A live dialog is stronger evidence than a successful join RPC.
                # Preserve verified membership in the existing dedupe journal.
                registry = read_registry()
                for handle, entry in registry["accounts"][label]["groups"].items():
                    if entry["status"] != "MEMBER_CONFIRMED":
                        continue
                    key = group_action_key(account_number, handle)
                    prior = group_record(state, "joined_groups", account_number, handle)
                    if prior is None:
                        state["joined_groups"][key] = {
                            "account": account_number,
                            "status": "verified_existing_member",
                            "group_id": entry["group_id"],
                            "membership_verified_at": entry["verified_at"],
                        }
                    else:
                        prior["status"] = "verified_existing_member"
                        prior["group_id"] = entry["group_id"]
                        prior["membership_verified_at"] = entry["verified_at"]
                        state["joined_groups"][key] = prior
                        legacy = state["joined_groups"].get(handle)
                        if (isinstance(legacy, dict)
                                and legacy.get("account") == account_number):
                            state["joined_groups"].pop(handle)
                save_state(path, state)
            except RegistryBlocked as exc:
                region_results[label] = {
                    "status": "BLOCKED", "reason": str(exc),
                }
            except Exception as exc:
                region_results[label] = {
                    "status": "ERROR", "reason": type(exc).__name__,
                }
                if _is_hard_stop(exc):
                    block_account(state, account_number, type(exc).__name__)
                    save_state(path, state)
        report["group_memberships"] = {
            "status": "CHECKED",
            "accounts": region_results,
        }

    # The opt-in model uses only this existing worker, its lock and its durable
    # state. A missing private growth_model.json means ZERO growth-model writes.
    report["organic_growth"] = {"status": "NOT_CONFIGURED"}
    if model is not None:
        report["organic_growth"] = {}
        for label, action, account_number in (
            ("owned_promotion", promote_owned_channel, model["publisher_account"]),
            ("join_requests", approve_pending_join_request,
             select_intake_account(state)),
        ):
            try:
                outcome = await action(
                    config, model, state, lambda value: save_state(path, value),
                    _connected_client,
                    tz=os.environ.get("TELEGRAM_TZ", "Europe/Lisbon"),
                )
                report["organic_growth"][label] = outcome
            except (PolicyBlocked, PolicyDeferred, ProbeBlocked) as exc:
                report["organic_growth"][label] = {
                    "status": "BLOCKED", "reason": str(exc),
                }
                save_state(path, state)
            except Exception as exc:
                if _is_hard_stop(exc):
                    reason = type(exc).__name__
                    if isinstance(exc, errors.FloodWaitError):
                        reason += f":{exc.seconds}s"
                    block_account(state, account_number, reason)
                report["organic_growth"][label] = {
                    "status": "ERROR", "reason": type(exc).__name__,
                }
                save_state(path, state)

    # Operator-listed groups and discoveries use the same existing worker.
    # Regional discovery can schedule each owner account independently.
    candidates = [(assigned_group_account(state, group), group) for group in groups]
    if discovery_enabled and regional_enabled:
        try:
            catalog = read_catalog(DEFAULT_CATALOG)
            for group, record in catalog["groups"].items():
                if not GROUP_RE.fullmatch(group) or not isinstance(record, dict):
                    continue
                tags = record.get("matched_regions", [])
                if not isinstance(tags, list):
                    continue
                for region, account in (("PT_ES", 1), ("EU_OTHER", 2)):
                    if region in tags:
                        candidates.append((account, group))
        except DiscoveryBlocked as exc:
            report["blocked"].append(
                {"scope": "group_catalog", "reason": str(exc)})

    handled = set()
    attempted_accounts = set()
    for account, group in candidates:
        canonical = group.casefold()
        pair = (account, canonical)
        if pair in handled:
            continue
        handled.add(pair)
        if (group_record(state, "joined_groups", account, canonical) is not None
                or group_record(state, "pending_group_actions", account, canonical) is not None):
            continue
        # One attempted join per worker cycle and account, not per day.
        # Keep real Telegram restrictions and the existing action interval.
        if account in attempted_accounts:
            continue
        attempted_accounts.add(account)
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
        "public_discovery": report.get("public_discovery"),
        "group_memberships": report.get("group_memberships"),
        "organic_growth": report.get("organic_growth"),
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


def public_cycle_summary(report: dict) -> dict:
    """Small sanitized stdout record; full details remain in private journal.

    PM2 stdout may be forwarded or retained outside the protected project vault.
    Never publish @handles, usernames, Telegram IDs or filesystem paths there.
    """
    groups = report.get("group_actions") or []
    members = report.get("member_actions") or []
    discovery = report.get("public_discovery")
    discovery_status = discovery.get("status") if isinstance(discovery, dict) else None
    if discovery_status not in {
        "PUBLIC_DISCOVERY_COMPLETE",
        "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
        "BLOCKED",
        "ERROR",
    }:
        discovery_status = "NOT_REPORTED"
    organic = report.get("organic_growth") or {}
    owned = organic.get("owned_promotion") if isinstance(organic, dict) else None
    intake = organic.get("join_requests") if isinstance(organic, dict) else None
    # Only stable status names and counters may reach the PM2 log.
    stable_statuses = {
        "NOT_CONFIGURED", "DISABLED", "OUTSIDE_POST_WINDOW",
        "OUTSIDE_JOIN_WINDOW", "ACCOUNT_BLOCKED", "ACCOUNT_INTERVAL",
        "ALREADY_POSTED_TODAY", "PREFLIGHT_ALREADY_ATTEMPTED_TODAY",
        "PENDING_MANUAL_RECONCILIATION", "POSTED", "APPROVED_REQUEST",
        "NO_PENDING_REQUESTS", "NEXT_SCAN_NOT_DUE", "POLICY_DEFERRED",
        "BLOCKED", "ERROR",
    }
    def status(value: dict | None) -> str:
        candidate = value.get("status") if isinstance(value, dict) else None
        return candidate if candidate in stable_statuses else "NOT_CONFIGURED"

    return {
        "status": "CYCLE",
        "public_discovery_status": discovery_status,
        "owned_promotion_status": status(owned),
        "join_request_status": status(intake),
        "owned_channel_posts": (
            1 if isinstance(owned, dict) and owned.get("status") == "POSTED" else 0
        ),
        "join_requests_approved": (
            1 if isinstance(intake, dict) and intake.get("status") == "APPROVED_REQUEST" else 0
        ),
        "join_request_approved_by_account": (
            intake["account"] if isinstance(intake, dict)
            and intake.get("status") == "APPROVED_REQUEST"
            and type(intake.get("account")) is int
            and intake["account"] in (1, 2) else None
        ),
        "owner_notice_status": (
            intake["owner_notice"] if isinstance(intake, dict)
            and intake.get("status") == "APPROVED_REQUEST"
            and intake.get("owner_notice") in {"ACCEPTED", "UNCERTAIN", "BLOCKED"}
            else "NOT_APPLICABLE"
        ),
        "group_actions_recorded": len(groups),
        "groups_joined": sum(item.get("status") == "joined" for item in groups),
        "member_actions_recorded": len(members),
        "members_added": sum(item.get("status") == "added" for item in members),
        "members_not_addable": sum(
            item.get("status") == "not_addable" for item in members
        ),
        "blocked_actions": len(report.get("blocked") or []),
    }


async def loop(vault: Path, interval: int) -> None:
    while True:
        try:
            report = await run_once(vault)
            print(json.dumps(public_cycle_summary(report), sort_keys=True), flush=True)
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
                    public_cycle_summary(asyncio.run(run_once(args.vault))),
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
