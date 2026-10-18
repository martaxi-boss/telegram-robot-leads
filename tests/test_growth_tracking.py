import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import growth_store as s
import growth_tracker as t
import optin_join_links as links

CHAT = '-100123456789'
TOKEN = 'NOT_REAL_SECRET_TOKEN'
LINK = 'https://t.me/+EXAMPLE_DO_NOT_SHARE'
TS = int(time.time())


def request(id, date=TS, link=LINK, uid=2468, chat=CHAT):
    return {'update_id': id, 'chat_join_request': {
        'chat': {'id': int(chat)}, 'date': date, 'from': {'id': uid, 'username': 'DO_NOT_STORE'},
        'invite_link': {'invite_link': link}}}


def member(id, before='left', after='member', link=None, uid=2468, chat=CHAT):
    data = {'update_id': id, 'chat_member': {
        'chat': {'id': int(chat)}, 'date': TS,
        'old_chat_member': {'status': before, 'user': {'id': uid}},
        'new_chat_member': {'status': after, 'user': {'id': uid}},
    }}
    if link:
        data['chat_member']['invite_link'] = {'invite_link': link}
    return data


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / s.DEFAULT_FILE
        self.db = s.open_store(self.path)
        self.addCleanup(self.db.close)
        s.register_campaign(self.db, CHAT, 'website', LINK)

    def test_db_stores_only_digests_and_owner_only(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        s.apply_updates(self.db, [request(10)], CHAT, TOKEN)
        self.db.close()
        blob = self.path.read_bytes()
        for sensitive in [LINK.encode(), b'DO_NOT_STORE', b'NOT_REAL_SECRET_TOKEN', b'2468']:
            self.assertNotIn(sensitive, blob)
        with self.assertRaises(PermissionError):
            self.path.chmod(0o644)
            s.open_store(self.path)

    def test_request_join_attributed_without_join_link(self):
        batch = [request(10), member(11)]
        self.assertEqual(s.apply_updates(self.db, batch, CHAT, TOKEN), 12)
        output = s.statistics(self.db)
        self.assertEqual(output['campaigns']['website']['requested'], 1)
        self.assertEqual(output['campaigns']['website']['joined'], 1)
        self.assertEqual(output['totals']['left'], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0], 0)
        self.assertEqual(s.next_offset(self.db), 12)
        # A Telegram retry must not count the same membership twice.
        s.apply_updates(self.db, batch, CHAT, TOKEN)
        self.assertEqual(s.statistics(self.db)['totals'], output['totals'])

    def test_unattributed_and_leave_correctly_labeled(self):
        s.apply_updates(self.db, [member(3, uid=777), member(4, before='member', after='left', uid=777)], CHAT, TOKEN)
        report = s.statistics(self.db)
        self.assertEqual(report['campaigns']['unattributed']['joined'], 1)
        self.assertEqual(report['campaigns']['unattributed']['left'], 1)
        self.assertIn('not unique persons', report['note'])

    def test_direct_link_member_join_is_attributed(self):
        s.apply_updates(self.db, [member(7, link=LINK, uid=777)], CHAT, TOKEN)
        self.assertEqual(s.statistics(self.db)['campaigns']['website']['joined'], 1)

    def test_wrong_group_and_status_updates_ignored(self):
        wrong = request(1, chat='-100999999')
        noop = member(2, before='member', after='administrator')
        s.apply_updates(self.db, [wrong, noop], CHAT, TOKEN)
        self.assertEqual(s.statistics(self.db)['totals'], {'requested': 0, 'joined': 0, 'left': 0})
        self.assertEqual(s.next_offset(self.db), 3)

    def test_transaction_rollback_and_replay(self):
        valid = request(9)
        invalid = member(10)
        invalid['chat_member']['new_chat_member'].pop('user')
        with self.assertRaises(ValueError):
            s.apply_updates(self.db, [valid, invalid], CHAT, TOKEN)
        self.assertIsNone(s.next_offset(self.db))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0], 0)
        s.apply_updates(self.db, [valid, member(10)], CHAT, TOKEN)
        self.assertEqual(s.next_offset(self.db), 11)
        self.assertEqual(s.statistics(self.db)['totals']['joined'], 1)

    def test_prune_old_events_and_pending(self):
        old = datetime.now(timezone.utc) - timedelta(days=100)
        self.db.execute('INSERT INTO events VALUES(999,?,?,?,?)', (CHAT, None, 'joined', old.isoformat()))
        self.db.execute('INSERT INTO pending VALUES(?,?,?,?)', (CHAT, 'old-member', None, old.isoformat()))
        self.db.commit()
        # Stats only reflect events in retention period even before cleanup.
        self.assertEqual(s.statistics(self.db)['totals']['joined'], 0)
        s.prune(self.db)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0], 0)

    def test_symlink_refused(self):
        elsewhere = Path(self.temp.name) / 'elsewhere.db'
        elsewhere.touch()
        bad = Path(self.temp.name) / 'link.db'
        bad.symlink_to(elsewhere)
        with self.assertRaises(OSError):
            s.open_store(bad)


class TrackerTests(unittest.TestCase):
    def test_permission_and_webhook_preflight(self):
        methods = []
        def api(method, params):
            methods.append(method)
            return {'id': 55} if method == 'getMe' else {'status': 'administrator', 'can_invite_users': True} if method == 'getChatMember' else {'url': ''} if method == 'getWebhookInfo' else {'id': int(CHAT)}
        self.assertEqual(t.verify_polling(api, '@iptvpncode'), CHAT)
        self.assertEqual(methods, ['getMe', 'getChatMember', 'getWebhookInfo', 'getChat'])
        def with_webhook(method, params):
            return {'url': 'https://example.org/already-running'} if method == 'getWebhookInfo' else api(method, params)
        with self.assertRaisesRegex(links.BotAccessError, 'Webhook already'):
            t.verify_polling(with_webhook, '@iptvpncode')

    def test_poll_once_commits_before_offset_advances(self):
        with tempfile.TemporaryDirectory() as td:
            with s.open_store(Path(td) / s.DEFAULT_FILE) as db:
                s.register_campaign(db, CHAT, 'website', LINK)
                seen = []
                def api(method, params):
                    self.assertEqual(method, 'getUpdates')
                    seen.append(dict(params))
                    return [request(100), member(101)] if len(seen) == 1 else []
                first = t.poll_once(db, api, CHAT, TOKEN)
                second = t.poll_once(db, api, CHAT, TOKEN)
                self.assertEqual(first['next_offset'], 102)
                self.assertEqual(second['metrics']['joined'], 1)
                self.assertNotIn('offset', seen[0])
                self.assertEqual(seen[1]['offset'], '102')
                self.assertIn('chat_member', seen[0]['allowed_updates'])

    def test_bot_api_supports_list_and_sanitizes_errors(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n): return json.dumps({'ok': True, 'result': [request(10)]}).encode()
        with patch('optin_join_links.urlopen', return_value=Response()):
            self.assertEqual(links.request_telegram(TOKEN, 'getUpdates', {}), [request(10)])
        from urllib.error import HTTPError
        with patch('optin_join_links.urlopen', side_effect=HTTPError('https://api.telegram.org/bot'+TOKEN+'/getUpdates', 409, 'Conflict', None, None)):
            with self.assertRaises(links.BotAccessError) as c:
                links.request_telegram(TOKEN, 'getUpdates', {})
            self.assertNotIn(TOKEN, str(c.exception))

    def test_link_cli_stores_digest_not_raw_url(self):
        with tempfile.TemporaryDirectory() as td:
            def api(token, method, payload, **kwargs):
                self.assertEqual(token, TOKEN)
                if method == 'getChat': return {'id': int(CHAT)}
                if method == 'getMe': return {'id': 55}
                if method == 'getChatMember': return {'status': 'administrator', 'can_invite_users': True}
                if method == 'createChatInviteLink': return {'invite_link': LINK}
                raise AssertionError(method)
            with patch.dict(os.environ, {'TELEGRAM_GROWTH_BOT_TOKEN': TOKEN, 'TARGET_GROUP': '@iptvpncode'}), \
                 patch('optin_join_links.request_telegram', side_effect=api), \
                 patch('sys.argv', ['optin_join_links.py', '--root', td, '--create-link', 'website']):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(links.main(), 0)
                output = json.loads(buf.getvalue())
                self.assertEqual(output['status'], 'created_and_registered')
                self.assertEqual(output['join_request_link'], LINK)
                self.assertNotIn(LINK.encode(), (Path(td) / s.DEFAULT_FILE).read_bytes())
                with s.open_store(Path(td) / s.DEFAULT_FILE) as db:
                    self.assertEqual(db.execute('SELECT name,chat_id FROM campaigns').fetchone(), ('website', CHAT))


if __name__ == '__main__':
    unittest.main()
