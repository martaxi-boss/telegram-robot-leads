#!/usr/bin/env python3
"""Telegram Robot Leads: verify existing user sessions without running legacy add/scrape.

Offline is the default. --online verifies the already-authorized accounts
without logging in, inviting, scraping or sending messages. --create-link is
an explicit, operator-initiated opt-in alternative, not an auto-add worker.
Only the project's own protected vault is read. Session databases are never
opened for writing or passed to Telethon's migrating SQLiteSession.
"""

import argparse
import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from lead_health import read_env_names_and_values

DEFAULT_VAULT = Path("/root/project-secrets/telegram-robot-leads")
ANDROID_PUBLIC_APP = (4, "014b35b6184100b085b0d0572f9b5103")
SESSION_NAME = re.compile(r"[A-Za-z0-9_-]{1,60}\Z")
GROUP_NAME = re.compile(r"@[A-Za-z][A-Za-z0-9_]{4,31}\Z")
ENV_ON = {"1", "yes", "on", "true"}


class ProbeBlocked(Exception):
    """A safe precondition was not met; its message contains no secrets."""


def _private_dir(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise ProbeBlocked("private_vault_path_invalid")
    try:
        st = path.lstat()
    except OSError as exc:
        raise ProbeBlocked("private_vault_missing") from exc
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) & 0o077):
        raise ProbeBlocked("private_vault_permissions_invalid")


def _private_file(path: Path, vault: Path, *, max_bytes: int = 131072) -> None:
    if path.parent != vault or path.is_symlink():
        raise ProbeBlocked("private_file_path_invalid")
    try:
        st = path.lstat()
    except OSError as exc:
        raise ProbeBlocked("private_file_missing") from exc
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) & 0o077):
        raise ProbeBlocked("private_file_permissions_invalid")
    if st.st_size < 1 or st.st_size > max_bytes:
        raise ProbeBlocked("private_file_size_invalid")


def _private_json(path: Path, vault: Path):
    _private_file(path, vault)
    if not hasattr(os, "O_NOFOLLOW"):
        raise ProbeBlocked("secure_file_open_unavailable")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _api_credentials(vault: Path, env: dict) -> tuple[int, str, str]:
    """Follow the original app's explicit API precedence, never print values."""
    if env.get("TELEGRAM_USE_PUBLISHED_ANDROID_API", "").lower() in ENV_ON:
        return *ANDROID_PUBLIC_APP, "published_android_fallback"
    try:
        api_id = int(env.get("TELEGRAM_API_ID") or env.get("API_ID") or "0")
    except ValueError:
        api_id = 0
    api_hash = env.get("TELEGRAM_API_HASH") or env.get("API_HASH") or ""
    if not api_id or not api_hash:
        filename = env.get("TELEGRAM_CREDENTIALS_FILE") or "telegram_api.json"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", filename):
            raise ProbeBlocked("credentials_filename_invalid")
        if (vault / filename).exists() or (vault / filename).is_symlink():
            data = _private_json(vault / filename, vault)
            if not isinstance(data, dict):
                raise ProbeBlocked("credentials_json_invalid")
            if not api_id:
                try:
                    api_id = int(data.get("api_id") or data.get("TELEGRAM_API_ID") or 0)
                except (TypeError, ValueError):
                    api_id = 0
            if not api_hash:
                api_hash = data.get("api_hash") or data.get("TELEGRAM_API_HASH") or ""
    if not (api_id > 0 and isinstance(api_hash, str)
            and re.fullmatch(r"[0-9a-fA-F]{32}", api_hash)):
        raise ProbeBlocked("app_api_credentials_missing_or_invalid")
    return api_id, api_hash, "private_app_credentials"


def _session_row(vault: Path, name: str) -> tuple[int, str, int, bytes]:
    if not SESSION_NAME.fullmatch(name):
        raise ProbeBlocked("session_name_invalid")
    path = vault / (name + ".session")
    _private_file(path, vault, max_bytes=128 * 1024 * 1024)
    if path.stat().st_size < 256:
        raise ProbeBlocked("session_file_too_small")
    # Immutable read: no WAL/lock/temp writes; old and new Telethon sessions
    # both have these four stable, explicitly selected SQLite columns.
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1",
                                     uri=True, timeout=5)) as db:
            db.execute("PRAGMA query_only=ON")
            row = db.execute(
                "SELECT dc_id, server_address, port, auth_key FROM sessions LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise ProbeBlocked("session_sqlite_unreadable") from exc
    if not row:
        raise ProbeBlocked("session_has_no_dc_key")
    dc, server, port, key = row
    if (type(dc) is not int or not 1 <= dc <= 100
            or not isinstance(server, str) or not re.fullmatch(r"[A-Za-z0-9.:-]{1,255}", server)
            or type(port) is not int or not 1 <= port <= 65535
            or not isinstance(key, bytes) or len(key) != 256):
        raise ProbeBlocked("session_dc_or_auth_key_invalid")
    return dc, server, port, key


def inspect(vault: Path = DEFAULT_VAULT) -> dict:
    _private_dir(vault)
    env = read_env_names_and_values(vault / ".env", owner_only=True)
    api_id, api_hash, source = _api_credentials(vault, env)
    raw = (json.loads(env["TELEGRAM_ACCOUNTS_JSON"])
           if env.get("TELEGRAM_ACCOUNTS_JSON")
           else _private_json(vault / "accounts.json", vault))
    if not isinstance(raw, list) or len(raw) != 2:
        raise ProbeBlocked("exactly_two_accounts_required")
    seen = set()
    entries = []
    for i, account in enumerate(raw, 1):
        if not isinstance(account, dict):
            raise ProbeBlocked("account_config_invalid")
        name = account.get("session")
        if not isinstance(name, str) or not SESSION_NAME.fullmatch(name) or name in seen:
            raise ProbeBlocked("duplicate_or_invalid_session")
        seen.add(name)
        row = _session_row(vault, name)
        entries.append({"index": i, "phone": str(account.get("phone") or ""),
                        "session": row})
    group = env.get("TARGET_GROUP") or "@iptvpncode"
    return {"api_id": api_id, "api_hash": api_hash, "api_source": source,
            "entries": entries, "group": group}


def public_offline_result(config: dict) -> dict:
    return {"status": "SESSION_FILES_READABLE_NOT_ONLINE_VERIFIED",
            "mode": "read_only_offline", "accounts": len(config["entries"]),
            "session_keys_present": len(config["entries"]),
            "api_source": config["api_source"],
            "app_owned_api_required_for_production": (
                config["api_source"] != "private_app_credentials"),
            "session_files_modified": False, "messages_sent": 0,
            "users_added": 0}


def make_memory_client(entry: dict, config: dict):
    from telethon import TelegramClient
    from telethon.crypto import AuthKey
    from telethon.sessions import MemorySession

    dc, address, port, key = entry["session"]
    memory = MemorySession()
    memory.set_dc(dc, address, port)
    memory.auth_key = AuthKey(data=key)
    return TelegramClient(memory, config["api_id"], config["api_hash"],
                          connection_retries=1, request_retries=0,
                          timeout=12, flood_sleep_threshold=0,
                          receive_updates=False)


async def check_one(config: dict, entry: dict, factory=make_memory_client) -> dict:
    result = {"account": entry["index"], "connected": False,
              "authorized": False, "phone_matches": None, "identity_verified": False}
    client = None
    try:
        client = factory(entry, config)
        await asyncio.wait_for(client.connect(), timeout=25)
        result["connected"] = bool(client.is_connected())
        if result["connected"]:
            result["authorized"] = bool(
                await asyncio.wait_for(client.is_user_authorized(), timeout=20))
        if result["authorized"]:
            me = await asyncio.wait_for(client.get_me(), timeout=20)
            result["identity_verified"] = bool(me and me.id and not me.deleted)
            expected = re.sub(r"\D", "", entry["phone"])
            found = re.sub(r"\D", "", str(getattr(me, "phone", "") or ""))
            result["phone_matches"] = expected == found if expected else None
        result["status"] = ("PASS" if result["identity_verified"]
                            and result["phone_matches"] is not False else "NOT_VERIFIED")
    except Exception as exc:
        result["status"] = "CHECK_FAILED"
        result["error_type"] = type(exc).__name__
    finally:
        if client is not None:
            try:
                if client.is_connected():
                    await asyncio.wait_for(client.disconnect(), timeout=10)
            except Exception:
                result["disconnect_status"] = "NOT_CONFIRMED"
    return result


async def check_both(config: dict, factory=make_memory_client) -> dict:
    # Sequential, network read-only. No login, sending, scraping or group edits.
    accounts = []
    for entry in config["entries"]:
        accounts.append(await check_one(config, entry, factory=factory))
    return {"status": "PASS" if all(a["status"] == "PASS" for a in accounts)
            else "NOT_VERIFIED", "mode": "online_read_only",
            "api_source": config["api_source"], "accounts": accounts,
            "session_files_modified": False, "messages_sent": 0,
            "users_added": 0}


async def create_voluntary_link(config: dict, title: str, factory=make_memory_client,
                                request_factory=None) -> str:
    """One explicit administrative action. Never add or message members."""
    if config["api_source"] != "private_app_credentials":
        raise ProbeBlocked("production_requires_own_api_credentials")
    if not isinstance(title, str) or not 1 <= len(title) <= 32 or not title.isprintable():
        raise ProbeBlocked("invalid_campaign_title")
    if not GROUP_NAME.fullmatch(config["group"]):
        raise ProbeBlocked("target_group_invalid")
    if request_factory is None:
        from telethon.tl.functions.messages import ExportChatInviteRequest
        request_factory = ExportChatInviteRequest
    client = factory(config["entries"][0], config)
    try:
        await asyncio.wait_for(client.connect(), timeout=25)
        if not await asyncio.wait_for(client.is_user_authorized(), timeout=20):
            raise ProbeBlocked("account_not_authorized")
        peer = await asyncio.wait_for(client.get_input_entity(config["group"]), timeout=20)
        invite = await asyncio.wait_for(
            client(request_factory(peer=peer, request_needed=True, title=title)),
            timeout=25)
        link = getattr(invite, "link", None)
        if not isinstance(link, str) or not link.startswith("https://t.me/"):
            raise ProbeBlocked("telegram_did_not_return_link")
        return link
    finally:
        if client.is_connected():
            await client.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--online", action="store_true",
                      help="Verify both Telegram sessions via get_me; no other actions")
    mode.add_argument("--create-link", metavar="TITLE",
                      help="Explicitly create one voluntary join-request link")
    parser.add_argument("--confirm-link-creation", action="store_true",
                        help="Required together with --create-link")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    args = parser.parse_args()
    try:
        config = inspect(args.vault)
        if args.create_link is not None:
            if not args.confirm_link_creation:
                raise ProbeBlocked("link_creation_requires_confirmation")
            link = asyncio.run(create_voluntary_link(config, args.create_link))
            print(json.dumps({"status": "CREATED", "request_needed": True, "link": link}))
            return 0
        if args.confirm_link_creation:
            raise ProbeBlocked("confirmation_without_link")
        outcome = (asyncio.run(check_both(config)) if args.online
                   else public_offline_result(config))
        print(json.dumps(outcome, sort_keys=True))
        return 0 if outcome["status"] in ("PASS", "SESSION_FILES_READABLE_NOT_ONLINE_VERIFIED") else 2
    except (ProbeBlocked, OSError, ValueError, TypeError, PermissionError,
            sqlite3.Error, ImportError, json.JSONDecodeError) as exc:
        reason = str(exc) if isinstance(exc, ProbeBlocked) else type(exc).__name__
        print(json.dumps({"status": "BLOCKED", "reason": reason}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
