#!/usr/bin/env python3
"""Official Telegram Bot API join-request links for VOLUNTARY group membership.

The default command performs read-only permission checks. No unsolicited invites,
contact scraping, auto-approvals, session impersonation, or anti-spam evasion.
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from lead_health import read_env_names_and_values
from growth_store import default_db_path, register_campaign, store_connection


class BotAccessError(RuntimeError):
    """Non-retryable Bot API or authorization error."""


class BotTransientError(BotAccessError):
    """Transport/server fault safe to retry for READ-ONLY polling only."""


def request_telegram(token: str, method: str, params: dict[str, str], timeout_sec: int = 15) -> Any:
    if not token or not token.strip():
        raise BotAccessError("Growth bot token is missing")
    if method not in {"getMe", "getChatMember", "getChat", "getWebhookInfo", "getUpdates", "createChatInviteLink"}:
        raise BotAccessError("Unrecognized Bot API operation")
    uri = f"https://api.telegram.org/bot{token}/{method}"
    req = Request(uri, data=urlencode(params).encode("utf-8"), method="POST")
    try:
        with urlopen(req, timeout=timeout_sec) as response:
            data = json.loads(response.read(1024 * 1024).decode("utf-8"))
    except HTTPError as exc:
        # HTTPError's URL includes the token: NEVER stringify the exception.
        if exc.code in {500, 502, 503, 504}:
            raise BotTransientError(f"Telegram API temporary HTTP {exc.code}") from None
        raise BotAccessError(f"Telegram API HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise BotTransientError("Telegram API temporarily unreachable") from None
    except ValueError:
        raise BotAccessError("Telegram API returned invalid JSON") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        code = data.get("error_code", "unknown") if isinstance(data, dict) else "unknown"
        raise BotAccessError(f"Telegram API refused {method} (code {code})")
    result = data.get("result")
    if method == "getUpdates":
        if not isinstance(result, list):
            raise BotAccessError("Telegram API response has unexpected shape")
    elif not isinstance(result, dict):
        raise BotAccessError("Telegram API response has unexpected shape")
    return result


def validate_dedicated_bot(token: str, configured: dict[str, str]) -> None:
    """Require explicit exclusive bot-token ownership; do not reveal token values."""
    explicit = os.environ.get("TELEGRAM_GROWTH_BOT_DEDICATED") or configured.get("TELEGRAM_GROWTH_BOT_DEDICATED", "0")
    if explicit.strip().lower() not in {"1", "true", "yes", "on"}:
        raise BotAccessError("Dedicated Telegram bot is not confirmed; refusing online preflight or polling")
    for key in ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "IPTVPN_BOT_TOKEN"):
        legacy = os.environ.get(key) or configured.get(key)
        if legacy and legacy == token:
            raise BotAccessError("Growth bot token is already configured for another Telegram bot")


def verify_target_group(api: Callable[[str, dict[str, str]], dict[str, Any]], chat_id: str) -> str:
    """Accept only verified numeric group/supergroup IDs; never a channel."""
    info = api("getChat", {"chat_id": chat_id})
    group_id = info.get("id")
    if not isinstance(group_id, int) or isinstance(group_id, bool):
        raise BotAccessError("Telegram did not confirm the numeric group ID")
    if info.get("type") not in {"group", "supergroup"}:
        raise BotAccessError("Target must be a Telegram group or supergroup")
    return str(group_id)


def check_access(api: Callable[[str, dict[str, str]], dict[str, Any]], chat_id: str) -> dict[str, str]:
    if not chat_id:
        raise BotAccessError("Set TARGET_GROUP to the target group")
    me = api("getMe", {})
    bot_id = me.get("id")
    if not isinstance(bot_id, int):
        raise BotAccessError("getMe did not return a bot ID")
    membership = api("getChatMember", {"chat_id": chat_id, "user_id": str(bot_id)})
    status = membership.get("status")
    if status not in {"administrator", "creator"}:
        raise BotAccessError("Bot must be an administrator of the target group")
    if status != "creator" and membership.get("can_invite_users") is not True:
        raise BotAccessError("Bot requires can_invite_users admin permission")
    return {"chat_id": chat_id, "bot_username": str(me.get("username") or "unknown"), "permission": "can_invite_users"}


def create_join_request_link(api: Callable[[str, dict[str, str]], dict[str, Any]], chat_id: str, campaign: str) -> str:
    if not campaign or not (1 <= len(campaign) <= 32) or any(ord(c) < 32 for c in campaign):
        raise BotAccessError("Campaign name must contain 1-32 printable characters")
    check_access(api, chat_id)
    result = api("createChatInviteLink", {
        "chat_id": chat_id,
        "name": campaign,
        "creates_join_request": "true",
    })
    link = result.get("invite_link")
    if not isinstance(link, str) or not link.startswith("https://t.me/"):
        raise BotAccessError("Telegram did not return a valid t.me invite link")
    return link


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Read-only credential and admin permission check (default)")
    group.add_argument("--create-link", metavar="CAMPAIGN", help="Create a named join-request link; users must choose to apply")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    configured = read_env_names_and_values(args.root / ".env")
    token = os.environ.get("TELEGRAM_GROWTH_BOT_TOKEN") or configured.get("TELEGRAM_GROWTH_BOT_TOKEN", "")
    chat = os.environ.get("TARGET_GROUP") or configured.get("TARGET_GROUP", "@iptvpncode")
    try:
        if not token:
            raise BotAccessError("TELEGRAM_GROWTH_BOT_TOKEN is not configured")
        validate_dedicated_bot(token, configured)
        def call(method: str, payload: dict[str, str]) -> dict[str, Any]:
            return request_telegram(token, method, payload)
        if args.create_link is not None:
            group_id = verify_target_group(call, chat)
            # Open database BEFORE calling Telegram; avoid creating a live link
            # when its local registry is unusable.
            with store_connection(default_db_path(args.root)) as db:
                link = create_join_request_link(call, chat, args.create_link)
                try:
                    register_campaign(db, group_id, args.create_link, link)
                except (sqlite3.Error, ValueError):
                    raise BotAccessError("Telegram link may exist but local registration failed: inspect invite links before retrying") from None
            print(json.dumps({"status": "created_and_registered", "join_request_link": link, "campaign": args.create_link}))
        else:
            check = check_access(call, chat)
            group_id = verify_target_group(call, chat)
            print(json.dumps({"status": "admin_rights_verified_for_group", "group_id": group_id,
                              "note": "No join event has been observed; dedicated ownership is operator-declared", **check}))
        return 0
    except (BotAccessError, sqlite3.Error, OSError, PermissionError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, BotAccessError) else "Local metrics storage or configuration failed"
        print(json.dumps({"status": "blocked", "reason": reason}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
