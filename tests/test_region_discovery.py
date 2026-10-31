"""Offline tests of regional public-group discovery with both existing sessions."""
import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import public_group_discovery as discovery


def group(handle):
    return SimpleNamespace(username=handle, title="IPTV public group",
                           megagroup=True, broadcast=False)


class FakeClient:
    def __init__(self, handle):
        self.handle = handle
        self.calls = []
        self.connected = False

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return True

    def is_connected(self):
        return self.connected

    async def __call__(self, request):
        self.calls.append(request)
        # The fake response also has users: the implementation must ignore them.
        return SimpleNamespace(
            chats=[group(self.handle)],
            users=[SimpleNamespace(username="private_user", phone="private")],
        )

    async def disconnect(self):
        self.connected = False


class RegionalDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.catalog = self.root / "state" / "groups.json"
        self.config = {
            "group": "@iptvpncode",
            "entries": [{"session": "first"}, {"session": "second"}],
        }
        self.clients = {
            "first": FakeClient("samegroup"),
            "second": FakeClient("samegroup"),
        }

    def factory(self, entry, _config):
        return self.clients[entry["session"]]

    def run_daily(self, account, region, day="2026-10-31"):
        return asyncio.run(discovery.discover_daily(
            self.config, self.vault, self.catalog,
            client_factory=self.factory, delay_seconds=0, day=day,
            account_number=account, region=region,
        ))

    def test_two_sessions_search_distinct_regional_keywords_and_share_catalog(self):
        pt = self.run_daily(1, "PT_ES")
        eu = self.run_daily(2, "EU_OTHER")
        self.assertEqual(pt["status"], "PUBLIC_DISCOVERY_COMPLETE")
        self.assertEqual(eu["status"], "PUBLIC_DISCOVERY_COMPLETE")
        self.assertEqual(pt["new_public_groups"], 1)
        self.assertEqual(eu["new_public_groups"], 0)
        self.assertEqual(
            [call.q for call in self.clients["first"].calls],
            list(discovery.REGIONAL_KEYWORDS["PT_ES"]),
        )
        self.assertEqual(
            [call.q for call in self.clients["second"].calls],
            list(discovery.REGIONAL_KEYWORDS["EU_OTHER"]),
        )
        self.assertTrue(all(isinstance(call, discovery.SearchRequest)
                            for client in self.clients.values()
                            for call in client.calls))
        saved = discovery.read_catalog(self.catalog)
        self.assertEqual(set(saved["groups"]), {"@samegroup"})
        self.assertEqual(
            saved["groups"]["@samegroup"]["matched_regions"],
            ["EU_OTHER", "PT_ES"],
        )
        self.assertEqual(saved["regional_attempts"], {"1": "2026-10-31",
                                                       "2": "2026-10-31"})
        self.assertNotIn("private_user", self.catalog.read_text())
        self.assertNotIn("private", self.catalog.read_text())
        self.assertFalse(self.clients["first"].connected)
        self.assertFalse(self.clients["second"].connected)

    def test_each_account_is_idempotent_on_same_day(self):
        self.run_daily(1, "PT_ES")
        self.run_daily(2, "EU_OTHER")
        count1 = len(self.clients["first"].calls)
        count2 = len(self.clients["second"].calls)
        self.assertEqual(
            self.run_daily(1, "PT_ES")["status"],
            "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
        )
        self.assertEqual(
            self.run_daily(2, "EU_OTHER")["status"],
            "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
        )
        self.assertEqual(len(self.clients["first"].calls), count1)
        self.assertEqual(len(self.clients["second"].calls), count2)

    def test_legacy_attempt_prevents_requery_of_account_one(self):
        discovery.write_catalog(self.catalog, {
            "schema": 1, "groups": {}, "last_scan_at": None,
            "last_attempt_day": "2026-10-31",
        })
        result = self.run_daily(1, "PT_ES")
        self.assertEqual(result["status"], "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY")
        self.assertEqual(self.clients["first"].calls, [])
        self.assertEqual(self.run_daily(2, "EU_OTHER")["status"],
                         "PUBLIC_DISCOVERY_COMPLETE")

    def test_wrong_account_region_pair_fails_before_network(self):
        for account, region in ((1, "EU_OTHER"), (2, "PT_ES"),
                                (0, "PT_ES"), (True, "PT_ES"),
                                (3, "EU_OTHER"), (1, "UNKNOWN")):
            with self.subTest(account=account, region=region):
                with self.assertRaises(discovery.DiscoveryBlocked):
                    self.run_daily(account, region)
        self.assertFalse(self.catalog.exists())
        self.assertEqual(self.clients["first"].calls, [])
        self.assertEqual(self.clients["second"].calls, [])

    def test_missing_session_is_not_reassigned_to_other_account(self):
        self.config["entries"] = self.config["entries"][:1]
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "session_missing"):
            self.run_daily(2, "EU_OTHER")
        self.assertEqual(self.clients["first"].calls, [])

    def test_regional_keywords_do_not_claim_verified_geography(self):
        self.assertEqual(len(discovery.REGIONAL_KEYWORDS["PT_ES"]), 3)
        self.assertGreaterEqual(len(discovery.REGIONAL_KEYWORDS["EU_OTHER"]), 4)
        with self.assertRaisesRegex(discovery.DiscoveryBlocked, "niche_unverified"):
            discovery.select_regional_keywords(self.vault, "@unrelated", "PT_ES")


if __name__ == "__main__":
    unittest.main()
