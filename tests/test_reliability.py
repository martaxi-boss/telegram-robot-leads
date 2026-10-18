"""Resilience and anti-collision tests for voluntary Telegram membership tracking."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import growth_tracker as t
import optin_join_links as links

CHAT = '-100123456789'
TOKEN = 'FAKE_TOKEN_TO_NEVER_USE'


class RecoveryTests(unittest.TestCase):
    def test_network_and_server_errors_are_transient_without_secret_leak(self):
        for failure, transient in (
            (URLError('error https://api.telegram.org/bot' + TOKEN), True),
            (HTTPError('https://api.telegram.org/bot' + TOKEN, 502, 'error', None, None), True),
            (HTTPError('https://api.telegram.org/bot' + TOKEN, 409, 'Conflict', None, None), False),
            (HTTPError('https://api.telegram.org/bot' + TOKEN, 429, 'Rate Limited', None, None), False),
        ):
            with self.subTest(code=getattr(failure, 'code', 'urlerror')):
                with patch('optin_join_links.urlopen', side_effect=failure):
                    with self.assertRaises(links.BotAccessError) as caught:
                        links.request_telegram(TOKEN, 'getUpdates', {})
                self.assertEqual(isinstance(caught.exception, links.BotTransientError), transient)
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_recovery_waits_and_resets_after_success(self):
        results = iter(['temporary', 'ok', 'temporary', 'ok', 'stop'])
        delays = []
        def polling(*args):
            outcome = next(results)
            if outcome == 'temporary':
                raise links.BotTransientError('transient')
            if outcome == 'stop':
                raise StopIteration
        with patch('growth_tracker.poll_once', side_effect=polling):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(StopIteration):
                    t.run_with_recovery(None, None, CHAT, TOKEN, sleep=delays.append)
        self.assertEqual(delays, [2, 2])

    def test_recovery_stops_after_bounded_retries(self):
        delays = []
        with patch('growth_tracker.poll_once', side_effect=links.BotTransientError('temporary')) as fake:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaisesRegex(links.BotAccessError, 'six bounded retries'):
                    t.run_with_recovery(None, None, CHAT, TOKEN, sleep=delays.append)
        self.assertEqual(fake.call_count, 7)
        self.assertEqual(delays, [2, 4, 8, 16, 32, 60])
        self.assertNotIn(TOKEN, err.getvalue())
        self.assertEqual(err.getvalue().count('temporary_poll_error'), 6)

    def test_non_retryable_bot_error_is_not_repeated(self):
        sleeps = []
        with patch('growth_tracker.poll_once', side_effect=links.BotAccessError('Telegram API HTTP 409')) as fake:
            with self.assertRaisesRegex(links.BotAccessError, '409'):
                t.run_with_recovery(None, None, CHAT, TOKEN, sleep=sleeps.append)
        self.assertEqual(fake.call_count, 1)
        self.assertEqual(sleeps, [])

    def test_writes_not_retried_when_telegram_service_unavailable(self):
        with patch('optin_join_links.urlopen', side_effect=HTTPError(
                'https://api.telegram.org/bot' + TOKEN, 503, 'unavailable', None, None)) as call:
            with self.assertRaises(links.BotTransientError):
                links.request_telegram(TOKEN, 'createChatInviteLink', {'chat_id': CHAT})
        self.assertEqual(call.call_count, 1)


class InviteSafetyTests(unittest.TestCase):
    def test_link_cli_blocks_shared_bot_token_before_any_telegram_call(self):
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': TOKEN, 'BOT_TOKEN': TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1', 'TARGET_GROUP': CHAT}
            with patch.dict(os.environ, env, clear=True), \
                 patch('sys.argv', ['optin_join_links.py', '--root', td, '--create-link', 'website']), \
                 patch('optin_join_links.request_telegram') as remote, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(links.main(), 2)
            remote.assert_not_called()
            self.assertIn('another Telegram bot', err.getvalue())
            self.assertNotIn(TOKEN, err.getvalue())

    def test_link_creation_refuses_channel_before_creating_link_or_db(self):
        def api(token, method, params, **kwargs):
            self.assertEqual(token, TOKEN)
            self.assertEqual(method, 'getChat')
            return {'id': int(CHAT), 'type': 'channel'}
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1', 'TARGET_GROUP': CHAT}
            with patch.dict(os.environ, env, clear=True), \
                 patch('sys.argv', ['optin_join_links.py', '--root', td, '--create-link', 'website']), \
                 patch('optin_join_links.request_telegram', side_effect=api) as remote, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(links.main(), 2)
            self.assertEqual(remote.call_count, 1)
            self.assertIn('group or supergroup', err.getvalue())
            self.assertFalse((Path(td) / 'growth_metrics.sqlite3').exists())

    def test_default_read_only_check_rejects_unconfirmed_bot(self):
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': TOKEN, 'TARGET_GROUP': CHAT}
            with patch.dict(os.environ, env, clear=True), \
                 patch('sys.argv', ['optin_join_links.py', '--root', td]), \
                 patch('optin_join_links.request_telegram') as remote, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(links.main(), 2)
            remote.assert_not_called()
            self.assertIn('not confirmed', err.getvalue())

    def test_readonly_bot_check_confirms_group_without_creating_state(self):
        calls=[]
        def api(token, method, params, **kwargs):
            calls.append(method)
            if method == 'getMe': return {'id': 222, 'username': 'growth_test'}
            if method == 'getChatMember': return {'status': 'administrator', 'can_invite_users': True}
            if method == 'getChat': return {'id': int(CHAT), 'type': 'supergroup'}
            raise AssertionError('Unexpected call')
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1', 'TARGET_GROUP': CHAT}
            with patch.dict(os.environ, env, clear=True), \
                 patch('sys.argv', ['optin_join_links.py', '--root', td, '--check']), \
                 patch('optin_join_links.request_telegram', side_effect=api), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(links.main(), 0)
            data=json.loads(out.getvalue())
            self.assertEqual(data['group_id'], CHAT)
            self.assertEqual(data['status'], 'admin_rights_verified_for_group')
            self.assertEqual(calls, ['getMe','getChatMember','getChat'])
            self.assertFalse((Path(td) / 'growth_metrics.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
