"""Offline verification of OWN account memberships, never third-party users."""
import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import member_groups as ledger
from public_group_discovery import write_catalog


class FakeClient:
    def __init__(self, dialogs=(), error=None):
        self.dialogs = list(dialogs)
        self.error = error
        self.calls = []
        self.connected = True
        self.disconnected = False

    async def get_dialogs(self, *, limit):
        self.calls.append(("get_dialogs", limit))
        if self.error:
            raise self.error
        return self.dialogs

    def is_connected(self):
        return self.connected

    async def disconnect(self):
        self.disconnected = True
        self.connected = False


def dialog(name, group_id, *, megagroup=True, broadcast=False):
    return SimpleNamespace(entity=SimpleNamespace(
        username=name, id=group_id, megagroup=megagroup, broadcast=broadcast))


class MembershipLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.catalog = self.home / "state" / "catalog.json"
        self.registry = self.home / "state" / "member-groups.json"
        self.config = {
            "group": "@iptvpncode",
            "entries": [{"session": "one"}, {"session": "two"}],
        }
        write_catalog(self.catalog, {
            "schema": 1, "last_scan_at": None,
            "groups": {
                "@publiciptv": {
                    "username": "@PublicIPTV",
                    "matched_regions": ["PT_ES"],
                    "title": "IPTV",
                    "url": "https://t.me/PublicIPTV",
                },
                "@euiptv": {
                    "username": "@EUIptv",
                    "matched_regions": ["EU_OTHER"],
                    "title": "IPTV",
                    "url": "https://t.me/EUIptv",
                },
            },
        })
        self.clients = {}
        self.connected_accounts = []

    async def connector(self, config, account_number):
        self.connected_accounts.append(account_number)
        return self.clients[account_number]

    def sync(self, number, day="2026-10-31"):
        return asyncio.run(ledger.sync_one(
            self.config, number, self.connector,
            registry_path=self.registry, catalog_path=self.catalog, day=day))

    def test_two_accounts_confirm_only_their_own_known_public_dialogs(self):
        self.clients[1] = FakeClient([
            dialog("PublicIPTV", 12345),
            dialog("privateGroup", 54321),
            dialog("iptvpncode", 98765),
            dialog("EUIptv", 0),
            dialog("EUIptv", True),
        ])
        self.clients[2] = FakeClient([dialog("EUIptv", 99999)])
        one = self.sync(1)
        two = self.sync(2)
        self.assertEqual([one["confirmed"], two["confirmed"]], [1, 1])
        reg = ledger.read_registry(self.registry)
        self.assertEqual(set(reg["accounts"]["1"]["groups"]), {"@publiciptv"})
        self.assertEqual(set(reg["accounts"]["2"]["groups"]), {"@euiptv"})
        self.assertEqual(
            reg["accounts"]["1"]["groups"]["@publiciptv"]["group_id"], 12345)
        self.assertEqual(
            reg["accounts"]["1"]["groups"]["@publiciptv"]["matched_search_regions"],
            ["PT_ES"])
        self.assertTrue(self.clients[1].disconnected)
        self.assertTrue(self.clients[2].disconnected)
        self.assertEqual(self.connected_accounts, [1, 2])
        self.assertNotIn("privateGroup", self.registry.read_text())
        self.assertNotIn("iptvpncode", self.registry.read_text())
        self.assertEqual(self.registry.stat().st_mode & 0o777, 0o600)

    def test_same_day_replay_does_not_reconnect(self):
        self.clients[1] = FakeClient([dialog("PublicIPTV", 20)])
        self.assertEqual(self.sync(1)["status"], "MEMBERSHIP_SCAN_COMPLETE")
        again = self.sync(1)
        self.assertEqual(again["status"], "MEMBERSHIP_ALREADY_SCANNED_TODAY")
        self.assertEqual(self.connected_accounts, [1])
        self.assertEqual(len(self.clients[1].calls), 1)

    def test_failures_preserve_no_retry_marker(self):
        self.clients[1] = FakeClient(error=TimeoutError("temporary"))
        with self.assertRaises(TimeoutError):
            self.sync(1)
        self.assertEqual(ledger.read_registry(self.registry)["accounts"]["1"]
                         ["last_attempt_day"], "2026-10-31")
        self.assertTrue(self.clients[1].disconnected)
        self.assertEqual(self.sync(1)["status"], "MEMBERSHIP_ALREADY_SCANNED_TODAY")
        self.assertEqual(self.connected_accounts, [1])

    def test_missing_dialog_next_day_is_not_claimed_to_be_departed(self):
        self.clients[1] = FakeClient([dialog("PublicIPTV", 321)])
        self.sync(1)
        self.clients[1] = FakeClient([])
        result = self.sync(1, day="2026-11-01")
        self.assertEqual(result["confirmed"], 0)
        self.assertEqual(result["not_reconfirmed"], 1)
        rec = ledger.read_registry(self.registry)["accounts"]["1"]["groups"]["@publiciptv"]
        self.assertEqual(rec["status"], "NOT_RECONFIRMED")
        self.assertEqual(rec["group_id"], 321)
        self.assertEqual(rec["verified_at"], "2026-10-31")

    def test_reconfirmation_after_unknown_keeps_stable_id(self):
        self.clients[1] = FakeClient([dialog("PublicIPTV", 555)])
        self.sync(1)
        self.clients[1] = FakeClient([])
        self.sync(1, day="2026-11-01")
        self.clients[1] = FakeClient([dialog("PublicIPTV", 555)])
        self.sync(1, day="2026-11-02")
        rec = ledger.read_registry(self.registry)["accounts"]["1"]["groups"]["@publiciptv"]
        self.assertEqual(rec["status"], "MEMBER_CONFIRMED")
        self.assertEqual(rec["verified_at"], "2026-11-02")

    def test_incomplete_dialog_list_is_not_called_complete(self):
        self.clients[1] = FakeClient([dialog("PublicIPTV", 555), dialog("EUIptv", 556)])
        with patch.object(ledger, "MAX_DIALOGS", 2):
            self.assertEqual(self.sync(1)["status"], "MEMBERSHIP_PARTIAL_DIALOG_LIMIT")

    def test_nonpublic_and_broadcast_dialogs_do_not_enter_registry(self):
        self.clients[2] = FakeClient([
            dialog("EUIptv", 777, megagroup=False),
            dialog("PublicIPTV", 789, broadcast=True),
        ])
        self.assertEqual(self.sync(2)["confirmed"], 0)
        self.assertEqual(ledger.read_registry(self.registry)["accounts"]["2"]["groups"], {})

    def test_reject_invalid_account_or_missing_session_without_network(self):
        self.clients[1] = FakeClient([])
        self.config["entries"] = self.config["entries"][:1]
        for account in (0, 2, 3, True, "1"):
            with self.subTest(account=account):
                with self.assertRaises(ledger.RegistryBlocked):
                    self.sync(account)
        self.assertFalse(self.registry.exists())
        self.assertEqual(self.connected_accounts, [])

    def test_private_registry_symlink_rejected(self):
        other = self.home / "outside"
        other.write_text("private")
        self.registry.symlink_to(other)
        with self.assertRaisesRegex(ledger.RegistryBlocked, "path_invalid"):
            ledger.read_registry(self.registry)
        with self.assertRaisesRegex(ledger.RegistryBlocked, "path_invalid"):
            ledger.save_registry(self.registry, ledger._empty())

    def test_readonly_status_aggregates_without_disclosing_group_names(self):
        import leads_operational_report as report
        self.clients[1] = FakeClient([dialog("PublicIPTV", 21)])
        self.sync(1)
        result = report._memberships(self.registry)
        self.assertEqual(result["status"], "READABLE")
        self.assertEqual(result["confirmed_total"], 1)
        self.assertEqual(result["accounts"]["1"]["confirmed"], 1)
        self.assertNotIn("@publiciptv", str(result))

    def test_no_member_collection_actions(self):
        self.clients[1] = FakeClient([dialog("PublicIPTV", 21)])
        self.sync(1)
        self.assertEqual(self.clients[1].calls, [("get_dialogs", ledger.MAX_DIALOGS)])
        self.assertNotIn("users", self.registry.read_text())
        self.assertNotIn("phone", self.registry.read_text())


if __name__ == "__main__":
    unittest.main()
