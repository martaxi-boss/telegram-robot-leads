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
    GetChatInviteImportersRequest,
    HideChatJoinRequestRequest,
)
from telethon.tl.types import InputUserEmpty

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
    if isinstance(previous, dict):
        if previous.get("status") == "pending":
            return _result("PENDING_MANUAL_RECONCILIATION")
        if previous.get("day") == day and previous.get("status") == "posted":
            return _result("ALREADY_POSTED_TODAY")
        if not isinstance(previous.get("day"), str) or previous.get("day") > day:
            raise PolicyBlocked("owned_promotion_state_invalid")
    last_action = float(state["accounts"][str(account_number)].get("last_action") or 0)
    if last_action and now - last_action < MIN_INTERVAL_SECONDS:
        return _result("ACCOUNT_INTERVAL")

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
        check_action(state, 1, "join_request_approval", now=now)
    except PolicyDeferred:
        return _result("POLICY_DEFERRED")
    # Account 1 is the designated intake operator. Never switch accounts
    # on account restrictions to bypass Telegram's safeguards.
    client = await connect(config, 1)
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
        state["join_request_last_scan"] = int(now)
        persist(state)
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
                "account": 1, "day": _day(now, tz),
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
            record_success(state, 1, "join_request_approval", now=now)
            state["approved_join_requests_done"][key] = {
                "status": "approved", "day": _day(now, tz),
            }
            state["pending_join_requests"].pop(key, None)
            persist(state)
            return _result("APPROVED_REQUEST", approvals_accepted=1)
        return _result("NO_PENDING_REQUESTS", approvals_accepted=0)
    finally:
        if client.is_connected():
            await client.disconnect()
