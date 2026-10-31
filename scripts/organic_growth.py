#!/usr/bin/env python3
"""Optional first-party Telegram growth model; never harvests third-party members.

The model can (a) publish a voluntary group link in ONE owner-authorized
broadcast channel and (b) approve ONE pending request made by a person to the
owner's destination group. There is no profile scraping, fake human behaviour,
external-group posting, message blasting or restriction evasion.

It is DISABLED unless a validated, owner-only growth_model.json is present in
the existing Telegram Robot Leads credential vault. The existing worker lock
and durable operation state are used; do not create another PM2 worker.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from telethon import errors, utils
from telethon.tl.functions.messages import (
    ExportChatInviteRequest,
    GetExportedChatInviteRequest,
    GetExportedChatInvitesRequest,
    GetChatInviteImportersRequest,
    HideChatJoinRequestRequest,
)
from telethon.tl.types import InputUserEmpty, InputUserSelf

from operation_policy import (
    DEFAULT_TZ,
    MIN_INTERVAL_SECONDS,
    PolicyBlocked,
    PolicyDeferred,
    check_action,
    record_success,
)
from telethon_sessions import ProbeBlocked

MODEL_FILE = "growth_model.json"
GROUP_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
SCAN_INTERVAL_SECONDS = 30 * 60
PROMOTION_HOUR = 12
MAX_PENDING_RESULTS = 20
VOLUNTARY_LINK_FILE = "voluntary_group_join_link.json"
VOLUNTARY_LINK_TITLE = "Leads voluntary request"
MAX_EXISTING_INVITES = 80
INVITE_LINK_RE = re.compile(r"https://t\.me/(?:\+|joinchat/)[A-Za-z0-9_-]{8,128}\Z")

# Original, non-deceptive copy; visible only in a channel explicitly selected
# by its administrator. These are not unsolicited private messages.
POSTS = (
    "A nossa comunidade partilha novidades e conversas sobre IPTV. "
    "Se quiseres participar no grupo, podes entrar por iniciativa própria: {url}",
    "Gostas de acompanhar novidades e trocar ideias sobre IPTV? "
    "O grupo da comunidade está aqui para quem quiser aderir: {url}",
    "Conversa com outros interessados nas novidades do mundo IPTV. "
    "A adesão ao nosso grupo é voluntária: {url}",
)


def read_model(vault: Path, target: str) -> dict[str, Any] | None:
    """Read the explicit operator-owned campaign file; absence disables it."""
    path = vault / MODEL_FILE
    if path.is_symlink():
        raise ProbeBlocked("growth_model_symlink_invalid")
    if not path.exists():
        return None
    if not hasattr(os, "O_NOFOLLOW"):
        raise ProbeBlocked("secure_file_open_unavailable")
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or not 1 <= info.st_size <= 2048):
                raise ProbeBlocked("growth_model_permissions_or_size_invalid")
            data = json.loads(stream.read().decode("utf-8"))
    except ProbeBlocked:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProbeBlocked("growth_model_unreadable") from exc
    if not isinstance(data, dict) or set(data) != {
        "schema", "target_group", "approve_join_requests",
        "owned_channel", "publish_in_owned_channel", "publisher_account"
    }:
        raise ProbeBlocked("growth_model_schema_invalid")
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise ProbeBlocked("growth_model_schema_invalid")
    group = data["target_group"]
    channel = data["owned_channel"]
    if not (isinstance(group, str) and GROUP_RE.fullmatch(group)
            and isinstance(target, str) and GROUP_RE.fullmatch(target)
            and group.casefold() == target.casefold()):
        raise ProbeBlocked("growth_model_target_mismatch")
    if type(data["approve_join_requests"]) is not bool:
        raise ProbeBlocked("growth_model_flag_invalid")
    if type(data["publish_in_owned_channel"]) is not bool:
        raise ProbeBlocked("growth_model_flag_invalid")
    if type(data["publisher_account"]) is not int or data["publisher_account"] not in (1, 2):
        raise ProbeBlocked("growth_model_account_invalid")
    if channel is not None and (
        not isinstance(channel, str)
        or not GROUP_RE.fullmatch(channel)
        or channel.casefold() == group.casefold()
    ):
        raise ProbeBlocked("growth_model_channel_invalid")
    if data["publish_in_owned_channel"] and not channel:
        raise ProbeBlocked("growth_model_owned_channel_required")
    if not data["approve_join_requests"] and not data["publish_in_owned_channel"]:
        raise ProbeBlocked("growth_model_no_features_enabled")
    return data


def preview(vault: Path, target: str) -> dict[str, Any]:
    """Offline readiness; no sessions or Telegram identity are used."""
    model = read_model(vault, target)
    if model is None:
        return {"status": "NOT_CONFIGURED", "enabled": False}
    return {
        "status": "CONFIGURED_NOT_ONLINE_VERIFIED",
        "enabled": True,
        "join_request_approval": model["approve_join_requests"],
        "owned_channel_promotion": model["publish_in_owned_channel"],
        "publisher_account": model["publisher_account"],
        # Avoid printing the channel's handle; see private vault only.
    }


def _hour(now: float, tz: str) -> int:
    return datetime.fromtimestamp(now, ZoneInfo(tz)).hour


def _day(now: float, tz: str) -> str:
    return datetime.fromtimestamp(now, ZoneInfo(tz)).date().isoformat()


def _result(status: str, **counts: int) -> dict[str, Any]:
    return {"status": status, **counts}


async def promote_owned_channel(
    config: dict,
    model: dict,
    state: dict,
    persist: Callable[[dict], None],
    connect: Callable[[dict, int], Awaitable[Any]],
    *,
    now: float | None = None,
    tz: str = DEFAULT_TZ,
) -> dict[str, Any]:
    """One group-link post per day in a verified admin-owned broadcast channel."""
    if not model["publish_in_owned_channel"]:
        return _result("DISABLED")
    channel = model["owned_channel"]
    account_number = model["publisher_account"]
    now = time.time() if now is None else now
    if not (PROMOTION_HOUR <= _hour(now, tz) < 22):
        return _result("OUTSIDE_POST_WINDOW")
    if state["accounts"][str(account_number)]["blocked"]:
        return _result("ACCOUNT_BLOCKED")
    previous = state["owned_promotion"].get(channel.casefold())
    day = _day(now, tz)
    if previous is not None:
        if (not isinstance(previous, dict)
                or previous.get("status") not in {"preflight", "pending", "posted"}
                or not isinstance(previous.get("day"), str)
                or previous["day"] > day):
            raise PolicyBlocked("owned_promotion_state_invalid")
        if previous["status"] == "pending":
            return _result("PENDING_MANUAL_RECONCILIATION")
        if previous["day"] == day and previous["status"] == "posted":
            return _result("ALREADY_POSTED_TODAY")
        if previous["day"] == day and previous["status"] == "preflight":
            return _result("PREFLIGHT_ALREADY_ATTEMPTED_TODAY")
    last_action = float(state["accounts"][str(account_number)].get("last_action") or 0)
    if last_action and now - last_action < MIN_INTERVAL_SECONDS:
        return _result("ACCOUNT_INTERVAL")

    # One preflight per day. In particular, missing admin rights must never
    # cause repeated Telegram queries every minute.
    state["owned_promotion"][channel.casefold()] = {
        "day": day, "status": "preflight", "account": account_number
    }
    persist(state)
    client = await connect(config, account_number)
    try:
        entity = await asyncio.wait_for(client.get_entity(channel), timeout=20)
        if getattr(entity, "broadcast", False) is not True or getattr(entity, "megagroup", False):
            raise ProbeBlocked("promotion_target_not_broadcast_channel")
        rights = getattr(entity, "admin_rights", None)
        if not (
            getattr(entity, "creator", False) is True
            or getattr(rights, "post_messages", False) is True
        ):
            raise ProbeBlocked("promotion_requires_channel_post_rights")

        from public_group_discovery import public_join_url
        link = public_join_url(config["group"])
        # The message is informative and transparent, never a disguised person.
        day_number = datetime.fromtimestamp(now, ZoneInfo(tz)).date().toordinal()
        message = POSTS[day_number % len(POSTS)].format(url=link)

        # A timeout after sending must not lead to an automatic duplicate post.
        state["owned_promotion"][channel.casefold()] = {
            "day": day, "status": "pending", "account": account_number
        }
        persist(state)
        posted = await asyncio.wait_for(
            client.send_message(entity, message, link_preview=False),
            timeout=25,
        )
        post_id = getattr(posted, "id", None)
        if type(post_id) is not int or post_id <= 0:
            raise PolicyBlocked("promotion_outcome_unknown_manual_review")
        state["owned_promotion"][channel.casefold()] = {
            "day": day, "status": "posted", "account": account_number,
            "message_id": post_id,
        }
        state["accounts"][str(account_number)]["last_action"] = int(now)
        persist(state)
        return _result("POSTED", posts_sent=1)
    finally:
        if client.is_connected():
            await client.disconnect()


def select_intake_account(state: dict) -> int:
    """Choose the least-used of the two existing authorised administrators.

    This is deterministic, not a fallback on Telegram account restrictions.
    """
    return min((sum(int(state["accounts"][str(number)][key])
                    for key in ("member_adds", "join_request_approvals")),
                number)
               for number in (1, 2))[1]


async def approve_pending_join_request(
    config: dict,
    model: dict,
    state: dict,
    persist: Callable[[dict], None],
    connect: Callable[[dict, int], Awaitable[Any]],
    *,
    now: float | None = None,
    tz: str = DEFAULT_TZ,
) -> dict[str, Any]:
    """Approve at most one *explicit* request to the user's own group.

    This only reads Telegram's pending-request queue for TARGET_GROUP.
    It does not query the participants of any third-party group.
    """
    if not model["approve_join_requests"]:
        return _result("DISABLED")
    # Do not use the second session to circumvent a restriction on either.
    if any(state["accounts"][str(number)]["blocked"] for number in (1, 2)):
        return _result("ACCOUNT_BLOCKED")
    account_number = select_intake_account(state)
    now = time.time() if now is None else now
    if not 8 <= _hour(now, tz) < 22:
        return _result("OUTSIDE_JOIN_WINDOW")
    # A potentially committed prior request is never automatically replayed.
    if state["pending_join_requests"]:
        return _result("PENDING_MANUAL_RECONCILIATION")
    last_scan = state["join_request_last_scan"]
    if type(last_scan) is not int or last_scan < 0 or last_scan > now + 60:
        raise PolicyBlocked("join_request_scan_invalid")
    if last_scan and now - last_scan < SCAN_INTERVAL_SECONDS:
        return _result("NEXT_SCAN_NOT_DUE")
    try:
        check_action(state, account_number, "join_request_approval", now=now)
    except PolicyDeferred:
        return _result("POLICY_DEFERRED")
    # Keep the account selected for this request fixed; never switch after
    # restrictions, rate limits or an uncertain remote outcome.
    # Mark the read attempt BEFORE the Telegram preflight. Permission/network
    # failures therefore receive a bounded 30-minute cooldown.
    state["join_request_last_scan"] = int(now)
    persist(state)
    client = await connect(config, account_number)
    try:
        group = await asyncio.wait_for(client.get_entity(config["group"]), timeout=20)
        if getattr(group, "megagroup", False) is not True or getattr(group, "broadcast", False):
            raise ProbeBlocked("join_request_target_not_supergroup")
        permissions = await asyncio.wait_for(
            client.get_permissions(group, "me"), timeout=20
        )
        if not (
            getattr(permissions, "is_creator", False) is True
            or (
                getattr(permissions, "is_admin", False) is True
                and getattr(permissions, "invite_users", False) is True
            )
        ):
            raise ProbeBlocked("join_request_admin_permission_missing")
        answer = await asyncio.wait_for(
            client(GetChatInviteImportersRequest(
                peer=group, requested=True, offset_date=0,
                offset_user=InputUserEmpty(), limit=MAX_PENDING_RESULTS,
            )), timeout=25,
        )
        importers = getattr(answer, "importers", None)
        users = getattr(answer, "users", None)
        if not isinstance(importers, (list, tuple)) or not isinstance(users, (list, tuple)):
            raise PolicyBlocked("join_request_response_invalid")
        # Never record usernames, bios, chats or profile data.
        pending_users = {
            getattr(u, "id", None): u for u in users
            if type(getattr(u, "id", None)) is int
        }
        for request in importers:
            if getattr(request, "requested", False) is not True:
                continue
            user_id = getattr(request, "user_id", None)
            if type(user_id) is not int or user_id <= 0:
                continue
            key = str(user_id)
            if key in state["approved_join_requests_done"]:
                continue
            user = pending_users.get(user_id)
            if user is None or getattr(user, "bot", False) or getattr(user, "deleted", False):
                continue
            try:
                input_user = utils.get_input_user(user)
            except (ValueError, TypeError):
                continue
            state["pending_join_requests"][key] = {
                "account": account_number, "day": _day(now, tz),
                "group": config["group"].casefold(),
            }
            persist(state)
            # One voluntary request per cycle. A successful RPC means the
            # approval was accepted, NOT that a membership event was observed.
            outcome = await asyncio.wait_for(
                client(HideChatJoinRequestRequest(
                    peer=group, user_id=input_user, approved=True,
                )), timeout=25,
            )
            if not isinstance(getattr(outcome, "updates", None), (list, tuple)):
                raise PolicyBlocked("join_request_outcome_unknown_manual_review")
            record_success(state, account_number, "join_request_approval", now=now)
            state["approved_join_requests_done"][key] = {
                "status": "approved", "day": _day(now, tz),
                "account": account_number,
            }
            state["pending_join_requests"].pop(key, None)
            persist(state)
            return _result("APPROVED_REQUEST", approvals_accepted=1,
                           account=account_number)
        return _result("NO_PENDING_REQUESTS", approvals_accepted=0)
    finally:
        if client.is_connected():
            await client.disconnect()


def _private_voluntary_link_path(vault: Path) -> Path:
    """Keep the reusable invitation hash inside the existing private vault."""
    if not vault.is_absolute() or vault.is_symlink():
        raise ProbeBlocked("voluntary_link_vault_invalid")
    parent = vault.stat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise ProbeBlocked("voluntary_link_vault_permissions_invalid")
    path = vault / VOLUNTARY_LINK_FILE
    if path.is_symlink():
        raise ProbeBlocked("voluntary_link_symlink_invalid")
    return path


def _read_voluntary_link(vault: Path, group: str) -> str | None:
    path = _private_voluntary_link_path(vault)
    if not path.exists():
        return None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or info.st_size > 2048):
                raise ProbeBlocked("voluntary_link_permissions_invalid")
            payload = json.loads(stream.read().decode("utf-8"))
    except ProbeBlocked:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProbeBlocked("voluntary_link_unreadable") from exc
    if (not isinstance(payload, dict)
            or set(payload) != {"schema", "target_group", "account", "link"}
            or type(payload["schema"]) is not int or payload["schema"] != 1
            or type(payload["account"]) is not int or payload["account"] != 1
            or payload["target_group"] != group.casefold()
            or not isinstance(payload["link"], str)
            or not INVITE_LINK_RE.fullmatch(payload["link"])):
        raise ProbeBlocked("voluntary_link_state_invalid")
    return payload["link"]


def _store_voluntary_link(vault: Path, group: str, link: str) -> None:
    """Create once; never replace an existing link, even after a crash."""
    path = _private_voluntary_link_path(vault)
    if not INVITE_LINK_RE.fullmatch(link):
        raise ProbeBlocked("voluntary_link_format_invalid")
    data = json.dumps({
        "schema": 1, "target_group": group.casefold(),
        "account": 1, "link": link,
    }, sort_keys=True).encode("utf-8")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ProbeBlocked("voluntary_link_state_changed_no_overwrite") from exc


def _request_required_invite(invite: Any) -> str:
    """Reject direct-join, expired or revoked invitations."""
    link = getattr(invite, "link", None)
    if (not isinstance(link, str) or not INVITE_LINK_RE.fullmatch(link)
            or getattr(invite, "request_needed", None) is not True
            or getattr(invite, "revoked", False) is True):
        raise ProbeBlocked("voluntary_link_not_an_active_approval_link")
    expiry = getattr(invite, "expire_date", None)
    if expiry is not None:
        if isinstance(expiry, datetime):
            if expiry.timestamp() <= time.time():
                raise ProbeBlocked("voluntary_link_expired")
        elif type(expiry) is int:
            if expiry <= int(time.time()):
                raise ProbeBlocked("voluntary_link_expired")
        else:
            raise ProbeBlocked("voluntary_link_expiry_invalid")
    return link


async def ensure_voluntary_request_link(
    config: dict, model: dict, vault: Path,
    connect: Callable[[dict, int], Awaitable[Any]],
) -> dict[str, Any]:
    """One-time setup of the owner's approval-only join link, using account 1.

    This function is intentionally NOT part of each worker cycle. It makes no
    posts and never sends requests to people. The existing run loop approves
    only user-initiated requests; it must not guess Telegram rate limits.
    """
    if (model.get("approve_join_requests") is not True
            or model.get("target_group", "").casefold() != config["group"].casefold()):
        raise ProbeBlocked("voluntary_link_model_not_enabled")
    saved = _read_voluntary_link(vault, config["group"])
    client = await connect(config, 1)
    try:
        group = await asyncio.wait_for(client.get_entity(config["group"]), timeout=20)
        if not getattr(group, "megagroup", False) or getattr(group, "broadcast", False):
            raise ProbeBlocked("voluntary_link_target_not_a_supergroup")
        permissions = await asyncio.wait_for(
            client.get_permissions(group, "me"), timeout=20,
        )
        if not (
            getattr(permissions, "is_creator", False) is True
            or (getattr(permissions, "is_admin", False) is True
                and getattr(permissions, "invite_users", False) is True)
        ):
            raise ProbeBlocked("voluntary_link_admin_permission_missing")

        if saved is not None:
            outcome = await asyncio.wait_for(
                client(GetExportedChatInviteRequest(peer=group, link=saved)),
                timeout=25,
            )
            remote_link = _request_required_invite(getattr(outcome, "invite", None))
            if remote_link != saved:
                raise ProbeBlocked("voluntary_link_remote_mismatch")
            return {"status": "EXISTING_VERIFIED", "request_needed": True,
                    "link_recorded": True, "created": 0, "members_added": 0}

        # Recovery after crash between Telegram link creation and local write:
        # reuse the single named link belonging to THIS account.
        previous = await asyncio.wait_for(
            client(GetExportedChatInvitesRequest(
                peer=group, admin_id=InputUserSelf(),
                revoked=False, limit=MAX_EXISTING_INVITES,
            )), timeout=25,
        )
        invites = getattr(previous, "invites", None)
        if not isinstance(invites, (list, tuple)):
            raise ProbeBlocked("voluntary_link_inventory_invalid")
        if len(invites) >= MAX_EXISTING_INVITES:
            raise ProbeBlocked("voluntary_link_inventory_incomplete")
        named = [item for item in invites
                 if getattr(item, "title", None) == VOLUNTARY_LINK_TITLE]
        if len(named) > 1:
            raise ProbeBlocked("voluntary_link_duplicate_named_links")
        if named:
            link = _request_required_invite(named[0])
            status = "REUSED"
        else:
            invite = await asyncio.wait_for(
                client(ExportChatInviteRequest(
                    peer=group, request_needed=True,
                    title=VOLUNTARY_LINK_TITLE,
                )), timeout=25,
            )
            link = _request_required_invite(invite)
            status = "CREATED"
        _store_voluntary_link(vault, config["group"], link)
        return {"status": status, "request_needed": True,
                "link_recorded": True, "created": int(status == "CREATED"),
                "members_added": 0}
    finally:
        if client.is_connected():
            await client.disconnect()
