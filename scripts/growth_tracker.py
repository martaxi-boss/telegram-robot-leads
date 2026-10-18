#!/usr/bin/env python3
"""Read-only Telegram Bot API polling and local opt-in membership metrics.

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
import sys
from typing import Any, Callable

from growth_store import apply_updates, default_db_path, next_offset, prune, statistics, store_connection
from lead_health import read_env_names_and_values
from optin_join_links import BotAccessError, check_access, request_telegram

ALLOWED_UPDATES = json.dumps(['chat_join_request', 'chat_member'])


def verify_polling(api: Callable[[str, dict[str, str]], Any], chat_id: str) -> str:
    """Fail closed when another integration uses a Telegram webhook."""
    check_access(api, chat_id)
    webhook = api('getWebhookInfo', {})
    if not isinstance(webhook, dict):
        raise BotAccessError('Telegram returned malformed webhook status')
    if webhook.get('url'):
        raise BotAccessError('Webhook already configured: do not consume another bot integration')
    chat = api('getChat', {'chat_id': chat_id})
    canonical_id = chat.get('id') if isinstance(chat, dict) else None
    if not isinstance(canonical_id, int) or isinstance(canonical_id, bool):
        raise BotAccessError('Cannot verify the numeric Telegram group ID')
    return str(canonical_id)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument('--check', action='store_true', help='Check Telegram bot rights/webhook without polling')
    choices.add_argument('--once', action='store_true', help='Receive and commit a single batch')
    choices.add_argument('--run', action='store_true', help='Continuously record membership transitions')
    choices.add_argument('--stats', action='store_true', help='Show local retained events (offline)')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
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
        configured = read_env_names_and_values(root / '.env')
        token = os.environ.get('TELEGRAM_GROWTH_BOT_TOKEN') or configured.get('TELEGRAM_GROWTH_BOT_TOKEN', '')
        group = os.environ.get('TARGET_GROUP') or configured.get('TARGET_GROUP', '@iptvpncode')
        if not token:
            raise BotAccessError('Dedicated Telegram growth bot token is missing')
        def api(method: str, data: dict[str, str]) -> Any:
            return request_telegram(token, method, data, timeout_sec=35)
        if args.check:
            chat_id = verify_polling(api, group)
            print(json.dumps({'status': 'ready', 'chat_id': chat_id,
                              'note': 'Checking does not prove delivery or ownership of update stream'}))
            return 0
        dedicated = os.environ.get('TELEGRAM_GROWTH_BOT_DEDICATED') or configured.get('TELEGRAM_GROWTH_BOT_DEDICATED', '0')
        if dedicated.strip().lower() not in {'1', 'true', 'yes', 'on'}:
            raise BotAccessError('Set TELEGRAM_GROWTH_BOT_DEDICATED=1 only for a bot with no other update consumer')
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
                    while True:
                        out = poll_once(db, api, chat_id, token)
                        if args.once:
                            print(json.dumps({'status': 'committed', **out}, ensure_ascii=False))
                            break
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
