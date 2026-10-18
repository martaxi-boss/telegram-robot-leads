import json
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
            self.assertEqual(result["configuration_candidates"]["MAX_ADDS_PROJECT_PER_DAY"]["value"], "17")
            self.assertFalse(result["credentials"]["connectivity_verified"])

    def test_pm2_dotenv_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text("MAX_ADDS_PROJECT_PER_DAY=42\n")
            p = {"name": "TELEGRAM-IPTVPN", "pid": 123, "pm2_env": {"status": "online", "DOTENV_OVERRIDE": "1", "MAX_ADDS_PROJECT_PER_DAY": "100"}}
            actual = lead_health.inspect(root, [p])
            self.assertEqual(actual["configuration_candidates"]["MAX_ADDS_PROJECT_PER_DAY"], {"value": "42", "source": ".env"})
            p["pm2_env"]["DOTENV_OVERRIDE"] = "0"
            actual = lead_health.inspect(root, [p])
            self.assertEqual(actual["configuration_candidates"]["MAX_ADDS_PROJECT_PER_DAY"], {"value": "100", "source": "pm2"})

    def test_database_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = sqlite3.connect(root / "users.db")
            db.executescript("CREATE TABLE users (user_id INTEGER PRIMARY KEY); INSERT INTO users VALUES (1); CREATE TABLE adder_daily (day TEXT, adds_ok INTEGER); INSERT INTO adder_daily VALUES ('2026-10-18', 5);")
            db.close()
            result = lead_health.inspect(root, [])
            self.assertEqual(result["database"]["candidate_count"], 1)
            self.assertEqual(result["database"]["last_accounting_additions"], 5)
            self.assertEqual(result["database"]["mode"], "read-only")

    def test_invalid_config_redacted(self):
        self.assertEqual(lead_health._safe_value("MAX_ADDS_PROJECT_PER_DAY", "password123"), "INVALID")
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

    def test_http_error_does_not_expose_token(self):
        from urllib.error import HTTPError
        with patch("optin_join_links.urlopen", side_effect=HTTPError("https://api.telegram.org/botTEST_SECRET/getMe", 401, "Unauthorized", None, None)):
            with self.assertRaises(optin_join_links.BotAccessError) as caught:
                optin_join_links.request_telegram("TEST_SECRET", "getMe", {})
            self.assertNotIn("TEST_SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
