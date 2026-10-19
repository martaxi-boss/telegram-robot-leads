"""Offline unit tests for bounded public group discovery (no Telegram network)."""
import asyncio
from contextlib import redirect_stdout
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
import public_group_discovery as discovery


def chat(name, *, title="Public IPTV group", group=True, broadcast=False):
    return SimpleNamespace(username=name, title=title, megagroup=group,
                           broadcast=broadcast)


class FakeClient:
    def __init__(self, results=None, authorized=True):
        self.results = results or []
        self.authorized = authorized
        self.connected = False
        self.calls = []
        self.disconnected = False

    async def connect(self):
        self.connected = True

    def is_connected(self):
        return self.connected

    async def is_user_authorized(self):
        return self.authorized

    async def __call__(self, request):
        self.calls.append(request)
        return self.results.pop(0)

    async def disconnect(self):
        self.disconnected = True
        self.connected = False


class PublicDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.path = self.root / "catalog" / "groups.json"
        self.config = {"group": "@iptvpncode", "entries": [{"session": "existing_1"},
                                                           {"session": "existing_2"}]}

    def test_existing_iptv_niche_gets_safe_keywords_without_configuration(self):
        self.assertEqual(
            discovery.select_keywords(self.vault, "@iptvpncode", []),
            ["iptv portugal", "iptv"],
        )

    def test_custom_private_keywords_are_deduplicated(self):
        file = self.vault / discovery.KEYWORDS_FILE
        file.write_text("# Public topics\nIPTV PT\niptv pt\nTV online\n", encoding="utf-8")
        file.chmod(0o600)
        self.assertEqual(discovery.select_keywords(self.vault, "@iptvpncode", []),
                         ["IPTV PT", "TV online"])
        file.chmod(0o644)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "permissions"):
            discovery.select_keywords(self.vault, "@iptvpncode", [])

    def test_no_unrelated_niche_is_inferred(self):
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "keywords_missing"):
            discovery.select_keywords(self.vault, "@randomgroup", [])

    def test_malformed_keywords_and_private_link_fail_closed(self):
        for terms in (["aa"], ["bad\nkeyword"], ["x" * 65], ["valid"] * 7):
            with self.subTest(terms=terms):
                with self.assertRaises(discovery.DiscoveryBlocked):
                    discovery.select_keywords(self.vault, "@iptvpncode", terms)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "target_not_a_public"):
            discovery.public_join_url("-100123456")

    def test_only_public_megagroup_metadata_is_retained(self):
        candidates = discovery.select_public_groups([
            chat("PublicIPTV"),
            chat("PublicIPTV", title="Duplicate"),
            chat("broadcasttv", group=False, broadcast=True),
            chat("private_channel", group=False),
            chat(None),
            chat("iptvpncode"),
            SimpleNamespace(username="@someperson", megagroup=False, title="User"),
            chat("OtherGroup", title="Name\nNewline"),
        ], "@iptvpncode", "iptv")
        self.assertEqual({x["username"] for x in candidates},
                         {"@PublicIPTV", "@OtherGroup"})
        self.assertEqual(candidates[1]["title"], "Name Newline")
        for item in candidates:
            self.assertEqual(set(item), {"username", "title", "url", "matched_keywords"})
            self.assertNotIn("user_id", item)

    def test_search_uses_existing_account_only_and_never_collects_users(self):
        fake = FakeClient([
            SimpleNamespace(chats=[chat("PublicIPTV"), chat("iptvpncode")],
                            users=[SimpleNamespace(id=123, phone="private",
                                                   username="private_person")]),
            SimpleNamespace(chats=[chat("publiciptv", title="Same group"),
                                   chat("AnotherPublic")],
                            users=[SimpleNamespace(id=456, phone="private2")]),
        ])
        result = asyncio.run(discovery.discover_once(
            self.config, ["iptv", "iptv portugal"], self.path,
            client_factory=lambda *args: fake, delay_seconds=0,
        ))
        self.assertEqual(result["new_public_groups"], 2)
        self.assertEqual(result["total_public_groups"], 2)
        self.assertEqual(result["voluntary_join_url"], "https://t.me/iptvpncode")
        self.assertEqual(result["members_collected"], 0)
        self.assertEqual(result["members_added"], 0)
        self.assertTrue(fake.disconnected)
        self.assertEqual(len(fake.calls), 2)
        self.assertTrue(all(isinstance(call, discovery.SearchRequest) for call in fake.calls))
        self.assertEqual([call.q for call in fake.calls], ["iptv", "iptv portugal"])
        saved = discovery.read_catalog(self.path)
        self.assertEqual(set(saved["groups"]), {"@publiciptv", "@anotherpublic"})
        self.assertEqual(set(saved["groups"]["@publiciptv"]["matched_keywords"]),
                         {"iptv", "iptv portugal"})
        self.assertNotIn("private_person", self.path.read_text())
        self.assertNotIn("private2", self.path.read_text())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.path.parent / "groups.json.lock").stat().st_mode & 0o777,
                         0o600)

    def test_second_pass_keeps_first_seen_and_does_not_duplicate(self):
        one = FakeClient([SimpleNamespace(chats=[chat("PublicIPTV")])])
        two = FakeClient([SimpleNamespace(chats=[chat("publiciptv")])])
        result_one = asyncio.run(discovery.discover_once(
            self.config, ["iptv"], self.path,
            client_factory=lambda *a: one, delay_seconds=0))
        first_seen = discovery.read_catalog(self.path)["groups"]["@publiciptv"]["first_seen_at"]
        result_two = asyncio.run(discovery.discover_once(
            self.config, ["iptv"], self.path,
            client_factory=lambda *a: two, delay_seconds=0))
        self.assertEqual(result_one["new_public_groups"], 1)
        self.assertEqual(result_two["new_public_groups"], 0)
        self.assertEqual(discovery.read_catalog(self.path)["groups"]["@publiciptv"]["first_seen_at"],
                         first_seen)

    def test_existing_account_authorization_required(self):
        fake = FakeClient(authorized=False)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "not_authorized"):
            asyncio.run(discovery.discover_once(
                self.config, ["iptv"], self.path,
                client_factory=lambda *a: fake, delay_seconds=0))
        self.assertTrue(fake.disconnected)
        self.assertEqual(fake.calls, [])

    def test_catalog_corruption_or_insecure_files_fail_closed(self):
        self.path.parent.mkdir(mode=0o700)
        self.path.write_text("{bad", encoding="utf-8")
        self.path.chmod(0o600)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "unreadable"):
            discovery.read_catalog(self.path)
        self.path.write_text('{"schema": 1, "groups": {}, "last_scan_at": null}')
        self.path.chmod(0o644)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "permissions"):
            discovery.read_catalog(self.path)

    def test_symlink_catalog_refused(self):
        self.path.parent.mkdir(mode=0o700)
        target = self.root / "other"
        target.write_text("private")
        self.path.symlink_to(target)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "symlink"):
            discovery.read_catalog(self.path)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "symlink"):
            discovery.write_catalog(self.path, {"schema": 1, "groups": {}})

    def test_preview_never_uses_telegram(self):
        with patch.object(discovery, "inspect", return_value=self.config):
            with patch.object(discovery, "make_memory_client") as client:
                with patch.object(sys, "argv",
                                  ["public_group_discovery.py", "--preview",
                                   "--vault", str(self.vault)]):
                    out = io.StringIO()
                    with redirect_stdout(out):
                        self.assertEqual(discovery.main(), 0)
                data = json.loads(out.getvalue())
                self.assertEqual(data["status"], "READY_OFFLINE")
                self.assertEqual(data["telegram_requests"], 0)
                client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
