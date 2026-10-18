"""Offline production-readiness regression tests (no real Telegram/VPS calls)."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import growth_tracker as tracker
from optin_join_links import BotAccessError

CHAT = '-100123456789'
BOT_TOKEN = 'FAKE_BOT_TOKEN_DO_NOT_USE'


def mock_api(method, params):
    if method == 'getMe':
        return {'id': 12345678, 'username': 'testgrowth'}
    if method == 'getChatMember':
        return {'status': 'administrator', 'can_invite_users': True}
    if method == 'getWebhookInfo':
        return {'url': ''}
    if method == 'getChat':
        return {'id': int(CHAT), 'type': 'supergroup'}
    raise AssertionError('Unexpected remote API method ' + method)


class ProductionGateTests(unittest.TestCase):
    def run_cli(self, td, args, env, api=mock_api):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch('sys.argv', ['growth_tracker.py', '--root', td, *args]), \
             patch('growth_tracker.request_telegram', side_effect=lambda token, method, payload, timeout_sec: api(method, payload)) as remote, \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = tracker.main()
        return code, out.getvalue(), err.getvalue(), remote.call_count

    def test_missing_dedicated_confirmation_blocks_check_before_api(self):
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': BOT_TOKEN, 'TARGET_GROUP': CHAT}
            code, out, err, calls = self.run_cli(td, ['--check'], env)
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertIn('not confirmed', err)
            self.assertNotIn(BOT_TOKEN, err)
            self.assertFalse((Path(td) / 'growth_metrics.sqlite3').exists())

    def test_reusing_another_bot_token_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': BOT_TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1',
                   'TELEGRAM_BOT_TOKEN': BOT_TOKEN, 'TARGET_GROUP': CHAT}
            code, _, err, calls = self.run_cli(td, ['--check'], env)
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertIn('another Telegram bot', err)
            self.assertNotIn(BOT_TOKEN, err)

    def test_checks_bot_and_group_without_consuming_updates(self):
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': BOT_TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1', 'TARGET_GROUP': CHAT}
            code, out, err, calls = self.run_cli(td, ['--check'], env)
            self.assertEqual(code, 0, err)
            self.assertEqual(calls, 4)
            report = json.loads(out)
            self.assertEqual(report['chat_id'], CHAT)
            self.assertEqual(report['status'], 'admin_and_local_storage_verified')
            self.assertIn('not remotely proven', report['note'])
            self.assertFalse((Path(td) / 'growth_metrics.sqlite3').exists())
            self.assertFalse((Path(td) / 'growth_metrics.lock').exists())

    def test_channel_is_not_valid_group_destination(self):
        def api(method, params):
            result = mock_api(method, params)
            if method == 'getChat':
                result['type'] = 'channel'
            return result
        with self.assertRaisesRegex(BotAccessError, 'group or supergroup'):
            tracker.verify_polling(api, CHAT)

    def test_unknown_chat_type_rejected(self):
        def api(method, params):
            result = mock_api(method, params)
            if method == 'getChat':
                result.pop('type')
            return result
        with self.assertRaisesRegex(BotAccessError, 'group or supergroup'):
            tracker.verify_polling(api, CHAT)

    def test_world_readable_database_is_rejected_before_api(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'growth_metrics.sqlite3'
            file.write_bytes(b'not-a-database')
            file.chmod(0o644)
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': BOT_TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1', 'TARGET_GROUP': CHAT}
            code, _, err, calls = self.run_cli(td, ['--check'], env)
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertIn('owner-only', err)

    def test_symlink_lockfile_rejected_before_api(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'arbitrary'
            target.touch()
            (Path(td) / 'growth_metrics.lock').symlink_to(target)
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': BOT_TOKEN,
                   'TELEGRAM_GROWTH_BOT_DEDICATED': '1', 'TARGET_GROUP': CHAT}
            code, _, err, calls = self.run_cli(td, ['--check'], env)
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertIn('symbolic link', err)

    def test_missing_confirmation_blocks_polling_and_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as td:
            env = {'TELEGRAM_GROWTH_BOT_TOKEN': BOT_TOKEN, 'TARGET_GROUP': CHAT}
            for action in ('--once', '--run'):
                code, _, err, calls = self.run_cli(td, [action], env)
                self.assertEqual(code, 2)
                self.assertEqual(calls, 0)
                self.assertIn('not confirmed', err)
            self.assertFalse((Path(td) / 'growth_metrics.sqlite3').exists())
            self.assertFalse((Path(td) / 'growth_metrics.lock').exists())

    def test_explicit_protected_vault_env_can_be_used_without_copying_token(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as vd:
            env_path = Path(vd) / '.env'
            env_path.write_text(
                'TELEGRAM_GROWTH_BOT_TOKEN=' + BOT_TOKEN + '\\n'
                + 'TELEGRAM_GROWTH_BOT_DEDICATED=1\\n'
                + 'TARGET_GROUP=' + CHAT + '\\n', encoding='utf-8')
            env_path.chmod(0o600)
            code, out, err, calls = self.run_cli(
                td, ['--check', '--env-file', str(env_path)], {})
            self.assertEqual(code, 0, err)
            self.assertEqual(calls, 4)
            self.assertEqual(json.loads(out)['chat_id'], CHAT)
            self.assertNotIn(BOT_TOKEN, out + err)
            self.assertFalse((Path(td) / 'growth_metrics.sqlite3').exists())

    def test_explicit_world_readable_vault_is_rejected_before_telegram_call(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as vd:
            env_path = Path(vd) / '.env'
            env_path.write_text('TELEGRAM_GROWTH_BOT_TOKEN=' + BOT_TOKEN + '\\n')
            env_path.chmod(0o644)
            code, out, err, calls = self.run_cli(
                td, ['--check', '--env-file', str(env_path)], {})
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertIn('configuration failed', err)
            self.assertNotIn(BOT_TOKEN, err)

    def test_explicit_symlink_vault_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as vd:
            original = Path(vd) / '.private'
            original.write_text('TELEGRAM_GROWTH_BOT_TOKEN=' + BOT_TOKEN)
            original.chmod(0o600)
            link = Path(vd) / '.env'
            link.symlink_to(original)
            code, out, err, calls = self.run_cli(
                td, ['--check', '--env-file', str(link)], {})
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertNotIn(BOT_TOKEN, err)

    def test_external_vault_cannot_authorize_reusing_existing_bot(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as vd:
            env_path = Path(vd) / '.env'
            env_path.write_text(
                'TELEGRAM_GROWTH_BOT_TOKEN=' + BOT_TOKEN + '\\n'
                + 'TELEGRAM_GROWTH_BOT_DEDICATED=1\\n'
                + 'TELEGRAM_BOT_TOKEN=' + BOT_TOKEN + '\\n', encoding='utf-8')
            env_path.chmod(0o600)
            code, out, err, calls = self.run_cli(
                td, ['--check', '--env-file', str(env_path)], {})
            self.assertEqual(code, 2)
            self.assertEqual(calls, 0)
            self.assertIn('another Telegram bot', err)
            self.assertNotIn(BOT_TOKEN, err)

    def test_stats_offline_never_needs_bot_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            code, out, err, calls = self.run_cli(td, ['--stats'], {})
            self.assertEqual(code, 0, err)
            self.assertEqual(calls, 0)
            self.assertEqual(json.loads(out)['status'], 'no_data')


if __name__ == '__main__':
    unittest.main()
