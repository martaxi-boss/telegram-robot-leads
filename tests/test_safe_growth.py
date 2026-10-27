import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import lead_health
import optin_join_links


class HealthTests(unittest.TestCase):
    def test_no_secret_value_in_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text(
                'TELEGRAM_API_HASH="TOP_SECRET_HERE"\nTELEGRAM_API_ID=1234\n'
                'TELEGRAM_GROWTH_BOT_TOKEN=BOT_TOKEN_PRIVATE\n'
                'MAX_ADDS_PROJECT_PER_DAY=17\n'
            )
            result = lead_health.inspect(root, [])
            data = json.dumps(result)
            self.assertNotIn("TOP_SECRET_HERE", data)
            self.assertNotIn("BOT_TOKEN_PRIVATE", data)
            self.assertTrue(result["credentials"]["telegram_api_hash_configured"])
            self.assertEqual(result["legacy_config_keys_present"], 1)
            self.assertNotIn("MAX_ADDS_PROJECT_PER_DAY", result["configuration_candidates"])
            self.assertNotIn("17", data)
            self.assertFalse(result["credentials"]["connectivity_verified"])

    def test_canonical_pm2_status_and_vault_group_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text("TARGET_GROUP=@vaultgroup" + chr(10))
            proc = {"name": "telegram-robot-leads", "pid": 123,
                    "pm2_env": {"status": "online", "TARGET_GROUP": "@othergroup"}}
            actual = lead_health.inspect(root, [proc])
            self.assertTrue(actual["runtime"]["found"])
            self.assertEqual(actual["runtime"]["status"], "online")
            self.assertEqual(actual["configuration_candidates"]["TARGET_GROUP"],
                             {"value": "@vaultgroup", "source": ".env"})
            self.assertFalse(actual["legacy_runtime"]["found"])


    def test_database_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = sqlite3.connect(root / "users.db")
            db.executescript("CREATE TABLE users (user_id INTEGER PRIMARY KEY); INSERT INTO users VALUES (1); CREATE TABLE adder_daily (day TEXT, adds_ok INTEGER); INSERT INTO adder_daily VALUES ('2026-10-18', 5);")
            db.close()
            result = lead_health.inspect(root, [])
            self.assertEqual(result["legacy_database_read_only"]["candidate_count"], 1)
            self.assertEqual(result["legacy_database_read_only"]["last_accounting_additions"], 5)
            self.assertEqual(result["legacy_database_read_only"]["mode"], "read-only")

    def test_secure_external_vault_file_requires_private_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = root / '.env'
            secret.write_text('TARGET_GROUP=@iptvpncode\n')
            secret.chmod(0o600)
            self.assertEqual(lead_health.read_env_names_and_values(
                secret, owner_only=True)['TARGET_GROUP'], '@iptvpncode')
            secret.chmod(0o644)
            with self.assertRaises(PermissionError):
                lead_health.read_env_names_and_values(secret, owner_only=True)
            secret.chmod(0o600)
            linked = root / 'linked.env'
            linked.symlink_to(secret)
            with self.assertRaises(PermissionError):
                lead_health.read_env_names_and_values(linked, owner_only=True)

    def test_secure_external_vault_rejects_unprivate_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = root / '.env'
            secret.write_text('TARGET_GROUP=@iptvpncode\n')
            secret.chmod(0o600)
            root.chmod(0o755)
            try:
                with self.assertRaises(PermissionError):
                    lead_health.read_env_names_and_values(secret, owner_only=True)
            finally:
                root.chmod(0o700)

    def test_health_default_never_queries_pm2(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with (
                patch('sys.argv', ['lead_health.py', '--root', directory]),
                patch('lead_health.read_pm2',
                      side_effect=AssertionError('PM2 must be opt-in')),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(lead_health.main(), 0)
            result = json.loads(output.getvalue())
            self.assertIn('not queried', result['runtime']['diagnostic'])

    def test_health_no_pm2_does_not_spawn_an_external_process(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with (
                patch('sys.argv', ['lead_health.py', '--root', directory, '--no-pm2']),
                patch('lead_health.read_pm2',
                      side_effect=AssertionError('PM2 must not be queried')),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(lead_health.main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report['project'], 'telegram-robot-leads')
            self.assertEqual(report['metrics_runtime']['status'], 'not_found')
            self.assertIn('not queried', report['runtime']['diagnostic'])

    def test_status_alias_never_opens_legacy_database_or_account_logs(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        legacy = (scripts / 'telegram-iptvpn-status.sh').read_text(encoding='utf-8')
        current = (scripts / 'telegram-robot-leads-status.sh').read_text(encoding='utf-8')
        self.assertIn('telegram-robot-leads-status.sh', legacy)
        self.assertNotIn('sqlite3.connect', legacy)
        self.assertNotIn('tail -', legacy)
        self.assertIn('--no-pm2', current)
        self.assertNotIn('--with-pm2', current)
        self.assertIn('/root/project-secrets/telegram-robot-leads', current)
        self.assertIn('--stats', current)

    def test_invalid_config_redacted(self):
        self.assertEqual(lead_health._safe_value("TELEGRAM_OPERATION_STATE", "/private/path"), "CONFIGURED")
        self.assertEqual(lead_health._safe_value("TARGET_GROUP", "SECRET&value"), "INVALID")


class OptInTests(unittest.TestCase):
    def test_read_only_check_does_not_create_link(self):
        calls = []
        def api(method, params):
            calls.append(method)
            return {"id": 42, "username": "growth"} if method == "getMe" else {"status": "administrator", "can_invite_users": True}
        result = optin_join_links.check_access(api, "@iptvpncode")
        self.assertEqual(result["bot_username"], "growth")
        self.assertEqual(calls, ["getMe", "getChatMember"])

    def test_link_is_opt_in_and_requires_join_request(self):
        calls = []
        def api(method, params):
            calls.append((method, params))
            if method == "getMe": return {"id": 42, "username": "growth"}
            if method == "getChatMember": return {"status": "administrator", "can_invite_users": True}
            return {"invite_link": "https://t.me/+ABC123"}
        link = optin_join_links.create_join_request_link(api, "@iptvpncode", "campaign1")
        self.assertEqual(link, "https://t.me/+ABC123")
        self.assertEqual(calls[-1][0], "createChatInviteLink")
        self.assertEqual(calls[-1][1]["creates_join_request"], "true")

    def test_missing_permission_blocks_creation(self):
        def api(method, params):
            return {"id": 42} if method == "getMe" else {"status": "administrator", "can_invite_users": False}
        with self.assertRaisesRegex(optin_join_links.BotAccessError, "can_invite_users"):
            optin_join_links.create_join_request_link(api, "@iptvpncode", "campaign1")

    def test_optin_check_reads_external_vault_without_copying_secrets(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as vault:
            token = 'FAKE_PRIVATE_12345'
            key = Path(vault) / '.env'
            key.write_text(
                'TELEGRAM_GROWTH_BOT_TOKEN=' + token + '\n'
                + 'TELEGRAM_GROWTH_BOT_DEDICATED=1\n'
                + 'TARGET_GROUP=@iptvpncode\n')
            key.chmod(0o600)
            methods = []
            def api(_token, method, payload):
                methods.append(method)
                if method == 'getMe':
                    return {'id': 12345, 'username': 'safe'}
                if method == 'getChatMember':
                    return {'status': 'administrator', 'can_invite_users': True}
                if method == 'getChat':
                    return {'id': -100234567890, 'type': 'supergroup'}
                raise AssertionError('Unexpected Telegram call')
            output = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch('sys.argv', ['optin_join_links.py', '--root', directory,
                                   '--env-file', str(key), '--check']),
                patch('optin_join_links.request_telegram', side_effect=api),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(optin_join_links.main(), 0)
            self.assertEqual(methods, ['getMe', 'getChatMember', 'getChat'])
            self.assertNotIn(token, output.getvalue())
            self.assertFalse((Path(directory) / 'growth_metrics.sqlite3').exists())

    def test_http_error_does_not_expose_token(self):
        from urllib.error import HTTPError
        with patch("optin_join_links.urlopen", side_effect=HTTPError("https://api.telegram.org/botTEST_SECRET/getMe", 401, "Unauthorized", None, None)):
            with self.assertRaises(optin_join_links.BotAccessError) as caught:
                optin_join_links.request_telegram("TEST_SECRET", "getMe", {})
            self.assertNotIn("TEST_SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
