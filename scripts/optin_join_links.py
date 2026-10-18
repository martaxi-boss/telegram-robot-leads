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
    pass


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
        raise BotAccessError(f"Telegram API HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise BotAccessError("Telegram API unavailable or returned invalid JSON") from None
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
        def call(method: str, payload: dict[str, str]) -> dict[str, Any]:
            return request_telegram(token, method, payload)
        if args.create_link is not None:
            group_info = call("getChat", {"chat_id": chat})
            group_id = group_info.get("id")
            if not isinstance(group_id, int) or isinstance(group_id, bool):
                raise BotAccessError("Telegram did not confirm the numeric group ID")
            # Open database BEFORE calling Telegram; avoid creating a live link
            # when its local registry is unusable.
            with store_connection(default_db_path(args.root)) as db:
                link = create_join_request_link(call, chat, args.create_link)
                try:
                    register_campaign(db, str(group_id), args.create_link, link)
                except (sqlite3.Error, ValueError):
                    raise BotAccessError("Telegram link may exist but local registration failed: inspect invite links before retrying") from None
            print(json.dumps({"status": "created_and_registered", "join_request_link": link, "campaign": args.create_link}))
        else:
            check = check_access(call, chat)
            print(json.dumps({"status": "ready_for_opt_in_links", **check}))
        return 0
    except (BotAccessError, sqlite3.Error, OSError, PermissionError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, BotAccessError) else "Local metrics storage or configuration failed"
        print(json.dumps({"status": "blocked", "reason": reason}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
