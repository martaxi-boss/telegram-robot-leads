"""Privacy-minimizing SQLite state for consent-based Telegram group growth.

Stores only update identifiers, group identifiers, event kinds, campaign names,
link SHA-256 digests and short-lived keyed member digests. Raw Telegram users,
phone numbers, usernames, API tokens, or private links are never persisted.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any, Iterator

DEFAULT_FILE = 'growth_metrics.sqlite3'
RETENTION_DAYS = 90
PENDING_DAYS = 30
KINDS = {'requested', 'joined', 'left'}


def default_db_path(root: Path) -> Path:
    return root / DEFAULT_FILE


def open_store(path: Path) -> sqlite3.Connection:
    """Initialize local metrics with owner-only permissions or fail closed."""
    path = Path(path)
    if path.is_symlink():
        raise OSError('Metrics database must not be a symlink')
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077 or not path.is_file():
            raise PermissionError('Metrics database permissions are not owner-only')
    else:
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        fd = os.open(path, flags, 0o600)
        os.close(fd)
    db = sqlite3.connect(str(path), timeout=10)
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY,
            chat_id TEXT NOT NULL,
            name TEXT NOT NULL,
            link_digest TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            update_id INTEGER PRIMARY KEY,
            chat_id TEXT NOT NULL,
            campaign_id INTEGER REFERENCES campaigns(id),
            kind TEXT NOT NULL CHECK(kind IN ('requested','joined','left')),
            occurred_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS events_date_idx ON events(occurred_at);
        CREATE TABLE IF NOT EXISTS pending (
            chat_id TEXT NOT NULL,
            member_digest TEXT NOT NULL,
            campaign_id INTEGER REFERENCES campaigns(id),
            requested_at TEXT NOT NULL,
            PRIMARY KEY(chat_id, member_digest)
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        );
    ''')
    return db


@contextmanager
def store_connection(path: Path) -> Iterator[sqlite3.Connection]:
    db = open_store(path)
    try:
        yield db
    finally:
        db.close()


def register_campaign(db: sqlite3.Connection, chat_id: str, name: str, link: str) -> None:
    if not isinstance(chat_id, str) or not chat_id.lstrip('-').isdigit():
        raise ValueError('Canonical numeric Telegram group ID is required')
    if not link.startswith('https://t.me/'):
        raise ValueError('Invalid Telegram invite link')
    if not name or len(name) > 32:
        raise ValueError('Campaign name must be 1-32 characters')
    digest = hashlib.sha256(link.encode('utf-8')).hexdigest()
    with db:
        db.execute('INSERT INTO campaigns(chat_id,name,link_digest,created_at) VALUES (?,?,?,?)',
                   (chat_id, name, digest, datetime.now(timezone.utc).isoformat()))


def _campaign_for_link(db: sqlite3.Connection, chat_id: str, link_object: Any) -> int | None:
    if not isinstance(link_object, dict):
        return None
    link = link_object.get('invite_link')
    if not isinstance(link, str):
        return None
    digest = hashlib.sha256(link.encode('utf-8')).hexdigest()
    row = db.execute('SELECT id FROM campaigns WHERE chat_id=? AND link_digest=?', (chat_id, digest)).fetchone()
    return int(row[0]) if row else None


def _member_digest(bot_token: str, chat_id: str, member_id: int) -> str:
    return hmac.new(bot_token.encode('utf-8'),
                    f'growth-member-v1:{chat_id}:{member_id}'.encode('ascii'),
                    hashlib.sha256).hexdigest()


def _active(member: Any) -> bool:
    if not isinstance(member, dict):
        return False
    status = member.get('status')
    if status in {'member', 'administrator', 'creator'}:
        return True
    return status == 'restricted' and member.get('is_member') is True


def _event_time(ts: Any) -> str:
    if not isinstance(ts, int) or isinstance(ts, bool) or ts < 0:
        raise ValueError('Invalid Telegram event time')
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _process_one(db: sqlite3.Connection, update: dict[str, Any], chat_id: str, token: str) -> None:
    identifier = update['update_id']
    if not isinstance(identifier, int) or isinstance(identifier, bool) or identifier < 0:
        raise ValueError('Invalid Telegram update identifier')
    request = update.get('chat_join_request')
    change = update.get('chat_member')
    if isinstance(request, dict) and isinstance(request.get('chat'), dict) and str(request['chat'].get('id')) == chat_id:
        member = request.get('from', {})
        member_id = member.get('id') if isinstance(member, dict) else None
        if not isinstance(member_id, int) or isinstance(member_id, bool):
            raise ValueError('Join request user ID missing')
        occurred_at = _event_time(request.get('date'))
        campaign = _campaign_for_link(db, chat_id, request.get('invite_link'))
        user_digest = _member_digest(token, chat_id, member_id)
        db.execute('''INSERT INTO pending(chat_id,member_digest,campaign_id,requested_at)
                      VALUES(?,?,?,?) ON CONFLICT(chat_id,member_digest) DO UPDATE SET
                      campaign_id=excluded.campaign_id, requested_at=excluded.requested_at''',
                   (chat_id, user_digest, campaign, occurred_at))
        db.execute('INSERT OR IGNORE INTO events(update_id,chat_id,campaign_id,kind,occurred_at) VALUES (?,?,?,?,?)',
                   (identifier, chat_id, campaign, 'requested', occurred_at))
        return
    if not isinstance(change, dict) or not isinstance(change.get('chat'), dict) or str(change['chat'].get('id')) != chat_id:
        return
    before, after = change.get('old_chat_member'), change.get('new_chat_member')
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError('Incomplete chat member status change')
    was, now = _active(before), _active(after)
    if was == now:
        return
    user = after.get('user')
    member_id = user.get('id') if isinstance(user, dict) else None
    if not isinstance(member_id, int) or isinstance(member_id, bool):
        raise ValueError('Chat member user ID missing')
    occurred_at = _event_time(change.get('date'))
    kind = 'joined' if now else 'left'
    campaign = _campaign_for_link(db, chat_id, change.get('invite_link')) if now else None
    if kind == 'joined':
        digest = _member_digest(token, chat_id, member_id)
        if campaign is None:
            pending = db.execute('SELECT campaign_id FROM pending WHERE chat_id=? AND member_digest=? AND requested_at >= ?',
                                 (chat_id, digest, (datetime.fromisoformat(occurred_at) - timedelta(days=PENDING_DAYS)).isoformat())).fetchone()
            campaign = pending[0] if pending else None
        db.execute('DELETE FROM pending WHERE chat_id=? AND member_digest=?', (chat_id, digest))
    db.execute('INSERT OR IGNORE INTO events(update_id,chat_id,campaign_id,kind,occurred_at) VALUES (?,?,?,?,?)',
               (identifier, chat_id, campaign, kind, occurred_at))


def next_offset(db: sqlite3.Connection) -> int | None:
    row = db.execute("SELECT value FROM checkpoints WHERE key='next_offset'").fetchone()
    return int(row[0]) if row else None


def apply_updates(db: sqlite3.Connection, updates: list[dict[str, Any]], chat_id: str, token: str) -> int | None:
    """Process a Telegram batch atomically; acknowledge it only on DB commit.

    A network response is *not* an acknowledgement. Only the next getUpdates
    invocation with the committed offset acknowledges processed updates.
    """
    if not isinstance(updates, list):
        raise ValueError('Telegram updates must be a list')
    prior = next_offset(db)
    last = prior
    ordered = sorted(updates, key=lambda u: u['update_id'] if isinstance(u, dict) and isinstance(u.get('update_id'), int) else -1)
    with db:
        for update in ordered:
            if not isinstance(update, dict) or not isinstance(update.get('update_id'), int) or isinstance(update['update_id'], bool) or update['update_id'] < 0:
                raise ValueError('Malformed Telegram update ID')
            update_id = update['update_id']
            if last is not None and update_id < last:
                continue
            _process_one(db, update, chat_id, token)
            last = update_id + 1
        if last != prior and last is not None:
            db.execute("INSERT INTO checkpoints(key,value) VALUES('next_offset',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (last,))
    return last


def prune(db: sqlite3.Connection, now: datetime | None = None) -> None:
    """Delete pseudonymous pending requests after 30 days and events after 90."""
    now = now or datetime.now(timezone.utc)
    with db:
        db.execute('DELETE FROM pending WHERE requested_at < ?', ((now-timedelta(days=PENDING_DAYS)).isoformat(),))
        db.execute('DELETE FROM events WHERE occurred_at < ?', ((now-timedelta(days=RETENTION_DAYS)).isoformat(),))


def statistics(db: sqlite3.Connection) -> dict[str, Any]:
    """Count observed transitions, never imply total current group membership."""
    counts = {'requested': 0, 'joined': 0, 'left': 0}
    by_campaign: dict[str, dict[str, int]] = {}
    for name, kind, count in db.execute('''
            SELECT COALESCE(c.name, 'unattributed'), e.kind, COUNT(*)
            FROM events e LEFT JOIN campaigns c ON c.id=e.campaign_id
            WHERE e.occurred_at >= ?
            GROUP BY COALESCE(c.name,'unattributed'), e.kind ORDER BY name, e.kind''',
            ((datetime.now(timezone.utc)-timedelta(days=RETENTION_DAYS)).isoformat(),)):
        counts[kind] += count
        by_campaign.setdefault(name, {'requested': 0, 'joined': 0, 'left': 0})[kind] += count
    return {'period': 'retained_events_last_90_days', 'totals': counts,
            'campaigns': by_campaign,
            'note': 'Observed join/leave transitions only; not unique persons or current member count'}
