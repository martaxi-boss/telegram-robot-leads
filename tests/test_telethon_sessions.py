import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import telethon_sessions as probe


class MemoryOnlySessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.chmod(self.root, 0o700)
        self.api_hash = "0123456789abcdef0123456789abcdef"
        env = (f"TELEGRAM_API_ID=12345\nTELEGRAM_API_HASH={self.api_hash}\n"
               "TARGET_GROUP=@iptvpncode\n")
        self.write_private(".env", env)
        self.write_private("accounts.json", json.dumps([
            {"session": "conta1", "phone": "+351912345678"},
            {"session": "conta2", "phone": "+351923456789"},
        ]))
        self.mk_session("conta1", old=True)
        self.mk_session("conta2", old=False)

    def write_private(self, name, value):
        path = self.root / name
        path.write_text(value, encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def mk_session(self, name, old):
        path = self.root / (name + ".session")
        db = sqlite3.connect(path)
        cols = ("dc_id INTEGER PRIMARY KEY, server_address TEXT, port INTEGER, "
                "auth_key BLOB, takeout_id INTEGER")
        if not old:
            cols += ", tmp_auth_key BLOB"
        db.execute("CREATE TABLE sessions (" + cols + ")")
        if old:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                       (2, "149.154.167.50", 443, b"a" * 256, None))
        else:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
                       (2, "149.154.167.50", 443, b"b" * 256, None, None))
        db.commit()
        db.close()
        os.chmod(path, 0o600)
        return path

    def test_both_legacy_and_newer_sqlite_schemas_load(self):
        cfg = probe.inspect(self.root)
        self.assertEqual(len(cfg["entries"]), 2)
        self.assertEqual(cfg["entries"][0]["session"][0], 2)
        self.assertEqual(len(cfg["entries"][0]["session"][3]), 256)
        self.assertEqual(len(cfg["entries"][1]["session"][3]), 256)
        self.assertEqual(cfg["api_source"], "private_app_credentials")

    def test_offline_is_readonly_redacted_and_does_not_create_lockfiles(self):
        existing = {x.name: (x.stat().st_size, x.stat().st_mtime_ns)
                    for x in self.root.iterdir()}
        data = probe.public_offline_result(probe.inspect(self.root))
        self.assertEqual(data["accounts"], 2)
        self.assertEqual(data["status"], "SESSION_FILES_READABLE_NOT_ONLINE_VERIFIED")
        self.assertNotIn(self.api_hash, json.dumps(data))
        self.assertNotIn("912345678", json.dumps(data))
        after = {x.name: (x.stat().st_size, x.stat().st_mtime_ns)
                 for x in self.root.iterdir()}
        self.assertEqual(existing, after)
        self.assertFalse(any(x.suffix in {".wal", ".shm"} for x in self.root.iterdir()))

    def test_large_realistic_sqlite_session_remains_usable_read_only(self):
        path = self.root / "conta1.session"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE entity_cache (payload BLOB)")
        db.execute("INSERT INTO entity_cache (payload) VALUES (?)", (b"x" * 350000,))
        db.commit()
        db.close()
        os.chmod(path, 0o600)
        before = (path.stat().st_size, path.stat().st_mtime_ns)
        self.assertGreater(before[0], 131072)
        result = probe.inspect(self.root)
        self.assertEqual(len(result["entries"][0]["session"][3]), 256)
        self.assertEqual((path.stat().st_size, path.stat().st_mtime_ns), before)

    def test_public_android_api_is_detected_not_allowed_for_production_links(self):
        self.write_private(".env", "TELEGRAM_USE_PUBLISHED_ANDROID_API=1\n"
                           "TARGET_GROUP=@iptvpncode\n")
        cfg = probe.inspect(self.root)
        self.assertEqual(cfg["api_source"], "published_android_fallback")
        with self.assertRaisesRegex(probe.ProbeBlocked, "own_api"):
            asyncio.run(probe.create_voluntary_link(cfg, "Campaign"))

    def test_bad_env_permissions_are_rejected(self):
        os.chmod(self.root / ".env", 0o644)
        with self.assertRaises((PermissionError, probe.ProbeBlocked)):
            probe.inspect(self.root)

    def test_bad_dir_permissions_are_rejected(self):
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(probe.ProbeBlocked, "vault_permissions"):
            probe.inspect(self.root)

    def test_symlinked_session_rejected_before_sqlite(self):
        target = self.root / "conta1.session"
        target.unlink()
        target.symlink_to(self.root / "conta2.session")
        with self.assertRaisesRegex(probe.ProbeBlocked, "path_invalid"):
            probe.inspect(self.root)

    def test_session_missing_auth_key_is_rejected(self):
        p = self.root / "conta1.session"
        db = sqlite3.connect(p)
        db.execute("UPDATE sessions SET auth_key=?", (b"x",))
        db.commit()
        db.close()
        with self.assertRaisesRegex(probe.ProbeBlocked, "auth_key_invalid"):
            probe.inspect(self.root)

    def test_duplicates_and_incorrect_account_count_are_rejected(self):
        self.write_private("accounts.json", json.dumps([{"session": "conta1"}]))
        with self.assertRaisesRegex(probe.ProbeBlocked, "two_accounts"):
            probe.inspect(self.root)
        self.write_private("accounts.json", json.dumps([
            {"session": "conta1"}, {"session": "conta1"}]))
        with self.assertRaisesRegex(probe.ProbeBlocked, "duplicate"):
            probe.inspect(self.root)

    def test_credentials_filename_must_be_local_safe(self):
        self.write_private(".env", "TELEGRAM_CREDENTIALS_FILE=../../another_project/.env\n")
        with self.assertRaisesRegex(probe.ProbeBlocked, "filename_invalid"):
            probe.inspect(self.root)

    def test_missing_api_is_blocked_not_guessed(self):
        self.write_private(".env", "TARGET_GROUP=@iptvpncode\n")
        with self.assertRaisesRegex(probe.ProbeBlocked, "api_credentials_missing"):
            probe.inspect(self.root)

    def test_online_sequential_fake_clients_verify_identifiers(self):
        config = probe.inspect(self.root)
        visited = []

        class FakeClient:
            def __init__(self, index):
                self.index = index
                self.active = False

            async def connect(self):
                visited.append(("connect", self.index))
                self.active = True

            def is_connected(self):
                return self.active

            async def is_user_authorized(self):
                return True

            async def get_me(self):
                phones = {1: "351912345678", 2: "351923456789"}
                return SimpleNamespace(id=self.index, deleted=False,
                                       phone=phones[self.index])

            async def disconnect(self):
                visited.append(("disconnect", self.index))
                self.active = False

        result = asyncio.run(probe.check_both(
            config, factory=lambda item, _: FakeClient(item["index"])))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(visited, [
            ("connect", 1), ("disconnect", 1),
            ("connect", 2), ("disconnect", 2)])
        self.assertTrue(all(x["authorized"] and x["phone_matches"]
                            for x in result["accounts"]))

    def test_online_detects_wrong_phone_without_printing_it(self):
        cfg = probe.inspect(self.root)

        class FakeClient:
            def __init__(self):
                self.active = False

            async def connect(self):
                self.active = True

            def is_connected(self):
                return self.active

            async def is_user_authorized(self):
                return True

            async def get_me(self):
                return SimpleNamespace(id=34, deleted=False, phone="351900000000")

            async def disconnect(self):
                self.active = False

        result = asyncio.run(probe.check_both(cfg, factory=lambda *_: FakeClient()))
        self.assertEqual(result["status"], "NOT_VERIFIED")
        self.assertFalse(result["accounts"][0]["phone_matches"])
        self.assertNotIn("351900000000", json.dumps(result))

    def test_link_creation_requires_operator_consent_and_request_needed(self):
        config = probe.inspect(self.root)
        calls = []

        class FakeClient:
            def __init__(self):
                self.active = False

            async def connect(self):
                self.active = True

            def is_connected(self):
                return self.active

            async def is_user_authorized(self):
                return True

            async def get_input_entity(self, target):
                self._target = target
                return target

            async def __call__(self, request):
                calls.append(request)
                return SimpleNamespace(link="https://t.me/+test_opt_in")

            async def disconnect(self):
                self.active = False

        link = asyncio.run(probe.create_voluntary_link(
            config, "my_campaign",
            factory=lambda *_: FakeClient(),
            request_factory=lambda **kw: kw))
        self.assertEqual(link, "https://t.me/+test_opt_in")
        self.assertEqual(calls, [{"peer": "@iptvpncode",
                                  "request_needed": True,
                                  "title": "my_campaign"}])

    def test_cli_create_link_requires_explicit_confirmation_without_network(self):
        with patch.object(sys, "argv", ["telethon_sessions.py", "--vault",
                                       str(self.root), "--create-link", "campaign"]):
            with patch.object(probe, "create_voluntary_link") as network:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    status = probe.main()
        self.assertEqual(status, 2)
        self.assertIn("link_creation_requires_confirmation", output.getvalue())
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
