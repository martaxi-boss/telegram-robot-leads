"""Offline regression checks for the Telegram-only growth radar."""
from datetime import datetime, timedelta, timezone
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import growth_radar as radar
import growth_store as store
from public_group_discovery import write_catalog

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
STAMP = "2026-10-27T12:00:00+00:00"


def group(username: str, title: str, topics: list[str], *, seen: str = STAMP) -> dict:
    return {
        "username": username, "title": title,
        "url": "https://t.me/" + username[1:],
        "matched_keywords": topics,
        "first_seen_at": seen, "last_seen_at": seen,
    }


class RankingTests(unittest.TestCase):
    def test_sorts_by_public_topic_relevance_without_members(self):
        catalog = {"groups": {
            "@iptvpt": group("@IPTVPT", "IPTV Portugal", ["iptv", "iptv portugal"]),
            "@streamingtv": group("@StreamingTV", "Streaming online", ["streaming"]),
            "@unrelated": group("@GenericGroup", "Unrelated", ["news"]),
        }}
        rows = radar.rank_public_groups(catalog, "@iptvpncode", now=NOW)
        self.assertEqual([r["group"] for r in rows], ["@IPTVPT", "@StreamingTV"])
        self.assertGreater(rows[0]["metadata_relevance_score"], rows[1]["metadata_relevance_score"])
        self.assertIsNone(rows[0]["members_estimate"])
        self.assertEqual(rows[0]["outreach"], "REQUIRES_GROUP_ADMIN_PERMISSION")
        for row in rows:
            self.assertEqual(set(row), {"group", "title", "public_url",
                                        "metadata_relevance_score", "signals",
                                        "members_estimate", "outreach"})

    def test_filters_target_and_unrelated_topics(self):
        catalog = {"groups": {
            "@iptvpncode": group("@iptvpncode", "IPTV Portugal", ["iptv"]),
            "@spam": group("@StreamingSpam", "IPTV Portugal Casino", ["iptv"]),
            "@localiptv": group("@LocalIPTV", "IPTV Portugal", ["iptv"]),
        }}
        rows = radar.rank_public_groups(catalog, "@iptvpncode", now=NOW)
        self.assertEqual([r["group"] for r in rows], ["@LocalIPTV"])

    def test_does_not_assume_audience_from_public_titles(self):
        catalog = {"groups": {
            "@iptvgroup": group("@IPTVGroup", "IPTV 500000 members", ["iptv"]),
        }}
        rows = radar.rank_public_groups(catalog, "@iptvpncode", now=NOW)
        self.assertEqual(rows[0]["members_estimate"], None)
        self.assertNotIn("500000", json.dumps(rows[0]["signals"]))

    def test_corrupt_entries_dropped_not_contacted(self):
        catalog = {"groups": {
            "@bad": group("@OTHER_NAME", "IPTV", ["iptv"]),
            "@entryiptv": group("@EntryIPTV", "IPTV", ["iptv"]),
            "@malformed": {"username": "@Malformed", "title": "IPTV", "matched_keywords": "iptv"},
        }}
        rows = radar.rank_public_groups(catalog, "@iptvpncode", now=NOW)
        self.assertEqual([r["group"] for r in rows], ["@EntryIPTV"])

    def test_stale_public_group_has_no_recency_bonus(self):
        rows = radar.rank_public_groups(
            {"groups": {"@oldiptv": group("@OldIPTV", "IPTV Portugal", ["iptv"],
                                       seen="2025-01-01T12:00:00+00:00"),
                        "@newiptv": group("@NewIPTV", "IPTV Portugal", ["iptv"])}},
            "@iptvpncode", now=NOW)
        self.assertEqual(rows[0]["group"], "@NewIPTV")
        self.assertEqual(rows[0]["metadata_relevance_score"] -
                         rows[1]["metadata_relevance_score"], 8)

    def test_bad_bounds_and_target_fail_closed(self):
        for target, limit in [("iptv", 12), ("@iptv", 12), ("@iptvpncode", 0),
                              ("@iptvpncode", 26)]:
            with self.assertRaises(radar.RadarBlocked):
                radar.rank_public_groups({"groups": {}}, target, now=NOW, limit=limit)

    def test_nonascii_public_topics_are_normalized(self):
        rows = radar.rank_public_groups(
            {"groups": {"@canaltvpt": group("@CanalTVPT", "Televisão Portuguesa e Séries",
                                       ["televisão portugal", "séries"])}},
            "@iptvpncode", now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertIn("televisao", rows[0]["signals"])


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "metrics.sqlite3"
        self.db = store.open_store(self.db_path)
        self.addCleanup(self.db.close)
        store.register_campaign(self.db, "-1001234567", "website",
                                "https://t.me/+FAKE_EXAMPLE")

    def _add(self, update_id: int, kind: str, when: datetime,
             campaign_name: str = "website") -> None:
        campaign_id = self.db.execute(
            "SELECT id FROM campaigns WHERE name=?", (campaign_name,)).fetchone()[0]
        with self.db:
            self.db.execute(
                "INSERT INTO events(update_id,chat_id,campaign_id,kind,occurred_at) VALUES (?,?,?,?,?)",
                (update_id, "-1001234567", campaign_id, kind, when.isoformat()))

    def test_7_30_day_observed_events_separate_from_estimates(self):
        self._add(1, "requested", NOW - timedelta(days=2))
        self._add(2, "joined", NOW - timedelta(days=2))
        self._add(3, "joined", NOW - timedelta(days=20))
        self._add(4, "joined", NOW - timedelta(days=40))
        self._add(5, "left", NOW - timedelta(days=2))
        result = radar.campaign_snapshot(self.db_path, now=NOW)
        self.assertEqual(result["status"], "OBSERVED_EVENTS")
        self.assertEqual(result["observed_joins_7d"], 1)
        self.assertEqual(result["observed_joins_30d"], 2)
        self.assertEqual(result["campaigns"][0]["requested_30d"], 1)
        self.assertEqual(result["campaigns"][0]["left_30d"], 1)
        self.assertIn("not current membership", result["note"])

    def test_db_remains_unchanged(self):
        self._add(1, "joined", NOW)
        self.db.commit()
        import hashlib
        digest_before = hashlib.sha256(self.db_path.read_bytes()).digest()
        result = radar.campaign_snapshot(self.db_path, now=NOW)
        digest_after = hashlib.sha256(self.db_path.read_bytes()).digest()
        self.assertEqual(digest_before, digest_after)
        self.assertEqual(result["observed_joins_30d"], 1)

    def test_missing_db_never_created(self):
        path = Path(self.temp.name) / "missing.sqlite3"
        result = radar.campaign_snapshot(path, now=NOW)
        self.assertEqual(result["status"], "NOT_CONFIGURED")
        self.assertFalse(path.exists())
        self.assertIsNone(result["observed_joins_30d"])

    def test_symlink_and_insecure_db_refused(self):
        alias = Path(self.temp.name) / "alias.sqlite3"
        alias.symlink_to(self.db_path)
        with self.assertRaisesRegex(radar.RadarBlocked, "symlink"):
            radar.campaign_snapshot(alias, now=NOW)
        self.db_path.chmod(0o644)
        with self.assertRaisesRegex(radar.RadarBlocked, "permissions"):
            radar.campaign_snapshot(self.db_path, now=NOW)

    def test_unknown_schema_refused(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DROP TABLE events")
        with self.assertRaisesRegex(radar.RadarBlocked, "schema"):
            radar.campaign_snapshot(self.db_path, now=NOW)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog_path = self.root / "public-groups.json"
        self.metrics_path = self.root / "no-metrics.sqlite3"

    def test_private_catalog_to_offline_report(self):
        write_catalog(self.catalog_path, {"schema": 1, "last_scan_at": STAMP,
            "groups": {
                "@sport": group("@SportsTV", "Football", ["sport"]),
                "@ptiptv": group("@PTIPTV", "IPTV Portugal", ["iptv portugal"]),
            }})
        result = radar.build_radar(catalog_path=self.catalog_path,
                                  metrics_db=self.metrics_path, now=NOW)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["telegram_requests"], 0)
        self.assertEqual(result["messages_sent"], 0)
        self.assertEqual(result["users_enumerated"], 0)
        self.assertEqual(result["public_groups_discovered"], 2)
        self.assertEqual(len(result["public_groups_ranked"]), 1)
        self.assertIn("ENABLE_OWN_GROUP_JOIN_EVENT_MEASUREMENT", result["next_steps"])
        self.assertEqual(stat.S_IMODE(self.catalog_path.stat().st_mode), 0o600)

    def test_missing_sources_do_not_claim_growth(self):
        result = radar.build_radar(catalog_path=self.catalog_path,
                                  metrics_db=self.metrics_path, now=NOW)
        self.assertEqual(result["catalog_status"], "NOT_CONFIGURED")
        self.assertIsNone(result["campaign_measurement"]["observed_joins_30d"])
        self.assertFalse(self.catalog_path.exists())

    def test_catalog_symlink_refused(self):
        real = self.root / "real.json"
        real.write_text("{}")
        self.catalog_path.symlink_to(real)
        with self.assertRaisesRegex(radar.RadarBlocked, "symlink"):
            radar.build_radar(catalog_path=self.catalog_path,
                              metrics_db=self.metrics_path, now=NOW)

    def test_cli_outputs_json_without_network_or_data_writes(self):
        buf = io.StringIO()
        with patch("sys.argv", ["growth_radar", "--catalog", str(self.catalog_path),
                                "--metrics-db", str(self.metrics_path)]), contextlib.redirect_stdout(buf):
            self.assertEqual(radar.main(), 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["status"], "OFFLINE_GROWTH_RADAR")
        self.assertEqual(result["users_enumerated"], 0)


if __name__ == "__main__":
    unittest.main()
