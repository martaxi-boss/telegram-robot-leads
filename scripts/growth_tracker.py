#!/usr/bin/env python3
"""Consent-based Telegram membership event tracking and local metrics.

Only watches explicit join requests/member status transitions for one group.
Does not approve, invite, message, scrape, or modify Telegram users.
Use a DEDICATED BotFather bot, never a token used by another update consumer.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time
from typing import Any, Callable

from growth_store import apply_updates, default_db_path, next_offset, prune, statistics, store_connection
from lead_health import read_env_names_and_values
from optin_join_links import BotAccessError, BotTransientError, check_access, request_telegram, validate_dedicated_bot, verify_target_group

ALLOWED_UPDATES = json.dumps(['chat_join_request', 'chat_member'])


def verify_polling(api: Callable[[str, dict[str, str]], Any], chat_id: str) -> str:
    """Fail closed when another integration uses a Telegram webhook."""
    check_access(api, chat_id)
    webhook = api('getWebhookInfo', {})
    if not isinstance(webhook, dict):
        raise BotAccessError('Telegram returned malformed webhook status')
    if webhook.get('url'):
        raise BotAccessError('Webhook already configured: do not consume another bot integration')
    return verify_target_group(api, chat_id)


def validate_storage(root: Path) -> None:
    """Non-mutating local storage preflight; no DB files or lockfiles created."""
    if not root.is_dir() or not os.access(root, os.W_OK | os.X_OK):
        raise BotAccessError('Local metrics directory is unavailable or unwritable')
    for filename in ('growth_metrics.sqlite3', 'growth_metrics.lock'):
        path = root / filename
        if path.is_symlink():
            raise BotAccessError('Local metrics storage has a symbolic link')
        if path.exists():
            try:
                info = path.stat()
            except OSError:
                raise BotAccessError('Local metrics storage is unreadable') from None
            if not path.is_file() or (stat.S_IMODE(info.st_mode) & 0o077):
                raise BotAccessError('Local metrics storage permissions must be owner-only')


def poll_once(db: sqlite3.Connection, api: Callable[[str, dict[str, str]], Any], chat_id: str, token: str) -> dict[str, Any]:
    last = next_offset(db)
    params = {'limit': '100', 'timeout': '20', 'allowed_updates': ALLOWED_UPDATES}
    if last is not None:
        params['offset'] = str(last)
    batch = api('getUpdates', params)
    if not isinstance(batch, list):
        raise BotAccessError('Telegram returned an invalid update batch')
    end = apply_updates(db, batch, chat_id, token)
    prune(db)
    return {'updates_received': len(batch), 'next_offset': end,
            'metrics': statistics(db)['totals']}


def run_with_recovery(db: sqlite3.Connection, api: Callable[[str, dict[str, str]], Any],
                      chat_id: str, token: str,
                      sleep: Callable[[float], None] = time.sleep) -> None:
    """Retry only temporary read-only polling faults with bounded backoff.

    Credentials/permissions, 409 poll conflicts and rate-limit errors fail
    immediately. No outbound membership-changing calls are made here.
    """
    transient_failures = 0
    while True:
        try:
            poll_once(db, api, chat_id, token)
        except BotTransientError:
            transient_failures += 1
            if transient_failures > 6:
                raise BotAccessError('Polling unavailable after six bounded retries') from None
            delay = min(2 ** transient_failures, 60)
            print(json.dumps({'status': 'temporary_poll_error',
                              'retry_in_seconds': delay,
                              'consecutive_failures': transient_failures}),
                  file=sys.stderr)
            sleep(delay)
        else:
            transient_failures = 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument('--check', action='store_true', help='Check Telegram bot rights/webhook without polling')
    choices.add_argument('--once', action='store_true', help='Receive and commit a single batch')
    choices.add_argument('--run', action='store_true', help='Continuously record membership transitions')
    choices.add_argument('--stats', action='store_true', help='Show local retained events (offline)')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--env-file', type=Path, default=None,
                        help='Optional absolute root-only .env path in the protected credentials vault')
    args = parser.parse_args()
    root = args.root.resolve()
    path = default_db_path(root)
    try:
        if args.stats:
            if not path.is_file():
                print(json.dumps({'status': 'no_data', 'metrics': {}}))
                return 0
            with store_connection(path) as db:
                print(json.dumps({'status': 'ok', **statistics(db)}, ensure_ascii=False))
            return 0
        env_path = args.env_file if args.env_file is not None else root / '.env'
        configured = read_env_names_and_values(env_path, owner_only=args.env_file is not None)
        token = os.environ.get('TELEGRAM_GROWTH_BOT_TOKEN') or configured.get('TELEGRAM_GROWTH_BOT_TOKEN', '')
        group = os.environ.get('TARGET_GROUP') or configured.get('TARGET_GROUP', '@iptvpncode')
        if not token:
            raise BotAccessError('Dedicated Telegram growth bot token is missing')
        validate_dedicated_bot(token, configured)
        validate_storage(root)
        def api(method: str, data: dict[str, str]) -> Any:
            return request_telegram(token, method, data, timeout_sec=35)
        if args.check:
            chat_id = verify_polling(api, group)
            print(json.dumps({'status': 'admin_and_local_storage_verified', 'chat_id': chat_id,
                              'note': 'Dedicated ownership is operator-declared, not remotely proven; no join event has been observed'}))
            return 0
        # Protect against parallel pollers on the same VPS. Also require a dedicated token
        # because file locking cannot guard pollers deployed elsewhere.
        lock_file = root / 'growth_metrics.lock'
        if lock_file.is_symlink():
            raise BotAccessError('Unsafe metrics lockfile')
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            with os.fdopen(fd, 'r+') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                chat_id = verify_polling(api, group)
                with store_connection(path) as db:
                    if args.once:
                        out = poll_once(db, api, chat_id, token)
                        print(json.dumps({'status': 'committed', **out}, ensure_ascii=False))
                    else:
                        run_with_recovery(db, api, chat_id, token)
                return 0
        except BlockingIOError:
            raise BotAccessError('Another local metrics poller holds the lock') from None
    except KeyboardInterrupt:
        return 130
    except (BotAccessError, sqlite3.Error, ValueError, PermissionError, OSError) as exc:
        # Errors from OS/sqlite may include filesystem paths. Never echo unknown
        # exception messages or raw Telegram API URLs (which embed bot tokens).
        reason = str(exc) if isinstance(exc, BotAccessError) else 'Local metrics storage or configuration failed'
        print(json.dumps({'status': 'blocked', 'reason': reason}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
