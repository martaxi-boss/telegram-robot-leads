"""Offline integration tests for opt-in-only migration; never call Telegram."""
import asyncio
from contextlib import redirect_stdout
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import consented_group_transfer as migration

SOURCE = "@SourceGroup"
TARGET = "@iptvpncode"


class ChannelParticipant:
    def __init__(self, user_id):
        self.user_id = user_id


class ChannelParticipantAdmin(ChannelParticipant):
    pass


class FakeClient:
    def __init__(self, *, is_admin=True, allowed=True, role="member",
                 bot=False, member_present=True):
        self.is_admin = is_admin
        self.allowed = allowed
        self.role = role
        self.bot = bot
        self.member_present = member_present
        self.connected = False
        self.requests = []
        self.disconnected = False
        self.permission_calls = 0
        self.account_checks = 0

    async def connect(self):
        self.connected = True

    def is_connected(self):
        return self.connected

    async def is_user_authorized(self):
        self.account_checks += 1
        return self.allowed

    async def get_entity(self, source):
        if source != SOURCE:
            raise AssertionError("Only approved source group may be resolved")
        return SimpleNamespace(megagroup=True, broadcast=False)

    async def get_permissions(self, group, who):
        self.permission_calls += 1
        self.requests.append(("admin", who))
        return SimpleNamespace(is_admin=self.is_admin, is_creator=False)

    async def get_input_entity(self, username):
        self.requests.append(("user", username))
        return SimpleNamespace(user_id=234567)

    async def __call__(self, req):
        if not isinstance(req, migration.GetParticipantRequest):
            raise AssertionError("Only read-only participant lookups are allowed")
        self.requests.append(("get_participant", req))
        cls = ChannelParticipantAdmin if self.role == "admin" else ChannelParticipant
        return SimpleNamespace(
            participant=cls(234567) if self.member_present else None,
            users=[SimpleNamespace(id=234567, bot=self.bot, deleted=False)],
        )

    async def disconnect(self):
        self.connected = False
        self.disconnected = True


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.consents = self.vault / migration.CONSENT_FILENAME
        self.consents.write_text(
            "@PersonOne|CONSENTED|@SourceGroup|2026-10-20|dm:101\n",
            encoding="utf-8",
        )
        self.consents.chmod(0o600)
        self.config = {
            "entries": [{"index": 1, "session": "existing_1"},
                        {"index": 2, "session": "existing_2"}],
            "group": TARGET,
            "api_source": "private_app_credentials",
        }
        self.verified = [dict(
            username="@PersonOne", source=SOURCE, reference="dm:101",
            date="2026-10-20",
        )]

    def test_explicit_consent_only_with_timestamp_and_source(self):
        rows = migration.read_consents(
            self.vault, SOURCE, today=date(2026, 10, 20)
        )
        self.assertEqual(rows, self.verified)
        with self.assertRaisesRegex(migration.TransferBlocked, "no_explicit"):
            migration.read_consents(self.vault, "@OtherSource", today=date(2026, 10, 20))

    def test_invalid_consent_marker_and_reference_rejected(self):
        bad = [
            "@PersonOne|APPROVED|@SourceGroup|2026-10-20|dm:101",
            "@PersonOne|CONSENTED|@SourceGroup|2026-10-20|external:101",
            "@PersonOne|CONSENTED|@SourceGroup|bad-date|dm:101",
            "@PersonOne|CONSENTED|@SourceGroup|2026-10-20|dm:0",
            "@Bad!|CONSENTED|@SourceGroup|2026-10-20|dm:101",
        ]
        for line in bad:
            with self.subTest(line=line):
                self.consents.write_text(line + "\n")
                with self.assertRaises(migration.TransferBlocked):
                    migration.read_consents(self.vault, SOURCE, today=date(2026, 10, 20))

    def test_old_future_duplicate_and_oversized_batches_rejected(self):
        for when in (date(2026, 1, 1), date(2026, 10, 21)):
            self.consents.write_text(
                "@PersonOne|CONSENTED|@SourceGroup|" + when.isoformat() + "|dm:101\n")
            with self.assertRaisesRegex(migration.TransferBlocked, "window"):
                migration.read_consents(self.vault, SOURCE, today=date(2026, 10, 20))
        self.consents.write_text(
            "@PersonOne|CONSENTED|@SourceGroup|2026-10-20|dm:101\n"
            "@personone|CONSENTED|@SourceGroup|2026-10-20|dm:102\n")
        with self.assertRaisesRegex(migration.TransferBlocked, "duplicate"):
            migration.read_consents(self.vault, SOURCE, today=date(2026, 10, 20))
        self.consents.write_text("".join(
            "@Person%04d|CONSENTED|@SourceGroup|2026-10-20|dm:%d\n" % (x, x)
            for x in range(11, 23)
        ))
        with self.assertRaisesRegex(migration.TransferBlocked, "too_many"):
            migration.read_consents(self.vault, SOURCE, today=date(2026, 10, 20))

    def test_consent_file_symlinks_and_bad_permissions_block(self):
        self.consents.chmod(0o644)
        with self.assertRaises(migration.TransferBlocked):
            migration.read_consents(self.vault, SOURCE, today=date(2026, 10, 20))
        self.consents.chmod(0o600)
        original = self.root / "external"
        original.write_text("TOP SECRET")
        self.consents.unlink()
        self.consents.symlink_to(original)
        with self.assertRaises(migration.TransferBlocked):
            migration.read_consents(self.vault, SOURCE, today=date(2026, 10, 20))
        self.assertEqual(original.read_text(), "TOP SECRET")

    def test_preview_uses_no_telegram_or_queue_writes(self):
        with (
            patch.object(migration, "inspect", side_effect=AssertionError("No session reads")),
            patch.object(migration, "make_memory_client",
                         side_effect=AssertionError("No Telegram client")),
            patch("sys.argv", ["migrate.py", "--preview", "--source", SOURCE,
                               "--vault", str(self.vault)]),
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                # Date uses the actual calendar; update consent date for the test.
                self.consents.write_text(
                    f"@PersonOne|CONSENTED|{SOURCE}|{date.today().isoformat()}|dm:101\n"
                )
                self.assertEqual(migration.main(), 0)
        status = json.loads(out.getvalue())
        self.assertEqual(status["telegram_requests"], 0)
        self.assertFalse((self.vault / "approved_users.txt").exists())

    def test_online_read_only_verifies_source_admin_and_exact_consent(self):
        fake = FakeClient()
        result = asyncio.run(migration.check_source_members(
            self.config, SOURCE, self.verified,
            client_factory=lambda *args: fake))
        self.assertEqual(result["eligible"], ["@PersonOne"])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["telegram_mutations"], 0)
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual([call[0] for call in fake.requests],
                         ["admin", "user", "get_participant"])
        self.assertTrue(fake.disconnected)

    def test_admin_permission_denial_stops_before_person_lookup(self):
        fake = FakeClient(is_admin=False)
        with self.assertRaisesRegex(migration.TransferBlocked, "admin_rights_missing"):
            asyncio.run(migration.check_source_members(
                self.config, SOURCE, self.verified,
                client_factory=lambda *args: fake))
        self.assertEqual([x[0] for x in fake.requests], ["admin"])
        self.assertTrue(fake.disconnected)

    def test_without_own_app_credentials_no_telegram_request(self):
        fake = FakeClient()
        config = {**self.config, "api_source": "published_android_fallback"}
        with self.assertRaisesRegex(migration.TransferBlocked, "own_telegram_app"):
            asyncio.run(migration.check_source_members(
                config, SOURCE, self.verified,
                client_factory=lambda *args: fake))
        self.assertEqual(fake.requests, [])
        self.assertFalse(fake.connected)

    def test_source_cannot_be_destination(self):
        fake = FakeClient()
        with self.assertRaisesRegex(migration.TransferBlocked, "source_equals_destination"):
            asyncio.run(migration.check_source_members(
                {**self.config, "group": SOURCE}, SOURCE, self.verified,
                client_factory=lambda *args: fake))
        self.assertEqual(fake.requests, [])

    def test_source_admin_user_is_excluded_even_if_consent_record_exists(self):
        fake = FakeClient(role="admin")
        result = asyncio.run(migration.check_source_members(
            self.config, SOURCE, self.verified,
            client_factory=lambda *args: fake))
        self.assertEqual(result["eligible"], [])
        self.assertEqual(result["excluded"], 1)
        self.assertTrue(fake.disconnected)

    def test_source_bot_or_not_member_cannot_enter_queue(self):
        for params in ({"bot": True}, {"member_present": False}):
            fake = FakeClient(**params)
            result = asyncio.run(migration.check_source_members(
                self.config, SOURCE, self.verified,
                client_factory=lambda *args: fake))
            self.assertEqual(result["eligible"], [])
            self.assertEqual(result["excluded"], 1)

    def test_queue_is_explicit_idempotent_private_and_preserves_comments(self):
        queue = self.vault / "approved_users.txt"
        queue.write_text("# Other preapproved account\n@AlreadyOne|APPROVED")
        queue.chmod(0o600)
        with self.assertRaisesRegex(migration.TransferBlocked, "confirmation"):
            migration.enqueue_verified_users(self.vault, ["@PersonOne"], confirm=False)
        self.assertNotIn("@PersonOne", queue.read_text())
        result = migration.enqueue_verified_users(
            self.vault, ["@PersonOne"], confirm=True)
        self.assertEqual(result["new_queued"], 1)
        self.assertEqual(result["members_added"], 0)
        self.assertEqual(queue.read_text(),
                         "# Other preapproved account\n@AlreadyOne|APPROVED\n"
                         "@PersonOne|CONSENTED\n")
        self.assertEqual(queue.stat().st_mode & 0o777, 0o600)
        repeated = migration.enqueue_verified_users(
            self.vault, ["@personone"], confirm=True)
        self.assertEqual(repeated["status"], "NO_NEW_OPTINS")
        self.assertEqual(queue.read_text().count("|CONSENTED"), 1)

    def test_insecure_or_invalid_existing_queue_is_never_replaced(self):
        queue = self.vault / "approved_users.txt"
        queue.write_text("@ExistingOne|CONSENTED\n")
        queue.chmod(0o644)
        with self.assertRaises(Exception):
            migration.enqueue_verified_users(self.vault, ["@PersonOne"], confirm=True)
        self.assertEqual(queue.read_text(), "@ExistingOne|CONSENTED\n")
        queue.chmod(0o600)
        queue.write_text("INVALID RECORD\n")
        with self.assertRaises(Exception):
            migration.enqueue_verified_users(self.vault, ["@PersonOne"], confirm=True)
        self.assertEqual(queue.read_text(), "INVALID RECORD\n")

    def test_queue_symlink_rejected_without_touching_target(self):
        external = self.root / "external"
        external.write_text("PRIVATE")
        queue = self.vault / "approved_users.txt"
        queue.symlink_to(external)
        with self.assertRaisesRegex(migration.TransferBlocked, "symlink"):
            migration.enqueue_verified_users(self.vault, ["@PersonOne"], confirm=True)
        self.assertEqual(external.read_text(), "PRIVATE")

    def test_incomplete_or_forged_remote_result_not_eligible(self):
        self.assertFalse(migration._eligible_participant(
            SimpleNamespace(participant=ChannelParticipant(42), users=[]), 42))
        self.assertFalse(migration._eligible_participant(
            SimpleNamespace(participant=ChannelParticipant(43), users=[
                SimpleNamespace(id=42, bot=False, deleted=False)
            ]), 42))
        self.assertFalse(migration._eligible_participant(
            SimpleNamespace(participant=ChannelParticipant(42), users=[
                SimpleNamespace(id=42, bot=False, deleted=True)
            ]), 42))


if __name__ == "__main__":
    unittest.main()
