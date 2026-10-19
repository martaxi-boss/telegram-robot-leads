"""Local, read-only certification: no Telegram calls, usernames or secrets emitted."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import leads_operational_report as report
from operation_policy import empty_state, save_state
from public_group_discovery import write_catalog

SHA = "a" * 40


class OperationalReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "runtime"
        self.checkout.mkdir(mode=0o700)
        self.marker = self.checkout / ".verified-source-commit"
        self.marker.write_text(SHA + "\n", encoding="ascii")
        self.marker.chmod(0o600)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.path = self.root / "state" / "catalog.json"
        self.path.parent.mkdir(mode=0o700)
        self.state = self.path.parent / "operation-state.json"
        self.events = self.path.parent / "supervisor-events.jsonl"
        write_catalog(self.path, {
            "schema": 1, "last_attempt_day": "2026-10-19",
            "last_scan_at": "2026-10-19T10:00:00+00:00",
            "groups": {"@pubgroup": {
                "username": "@pubgroup", "title": "Very Private Lookup Term",
                "url": "https://t.me/pubgroup", "first_seen_at": "2026-10-19",
                "last_seen_at": "2026-10-19",
                "matched_keywords": ["Private Campaign Keyword"]
            }},
        })
        state = empty_state()
        state["pending_member_actions"]["@sensitive_person"] = {"status": "pending"}
        save_state(self.state, state)
        self.now = 1792420000.0
        os.utime(self.marker, (self.now - 120, self.now - 120))
        self.events.write_text(json.dumps({
            "ts": int(self.now) - 20,
            "event": {
                "kind": "cycle", "group_actions": [{"group": "@secretGroup"}],
                "member_actions": [{"user": "@secret_person", "status": "approved"}],
                "blocked": [], "public_discovery": {
                    "status": "PUBLIC_DISCOVERY_COMPLETE",
                    "voluntary_join_url": "https://t.me/iptvpncode",
                    "private_api_hash": "ABSOLUTE_SECRET_VALUE"},
            },
        }) + "\n", encoding="utf-8")
        self.events.chmod(0o600)
        self.valid_config = {
            "group": "@iptvpncode",
            "entries": [{"index": 1}, {"index": 2}],
            "api_source": "published_android_fallback",
        }

    def build(self, **overrides):
        params = dict(vault=self.vault, checkout=self.checkout,
                      catalog_path=self.path, state_path=self.state,
                      events_path=self.events, expected_sha=SHA,
                      now=self.now,
                      pm2_records=[{"name": "telegram-robot-leads",
                                    "pm2_env": {"status": "online",
                                                "restart_time": 0}}])
        params.update(overrides)
        with patch.object(report, "inspect", return_value=self.valid_config) as fake:
            result = report.build_report(**params)
            fake.assert_called_once_with(self.vault)
            return result

    def test_live_evidence_requires_fresh_cycle_and_provenance(self):
        result = self.build()
        self.assertEqual(result["status"], "LIVE_PUBLIC_DISCOVERY_OBSERVED")
        self.assertEqual(result["public_discovery"]["public_groups"], 1)
        self.assertEqual(result["operation_state"]["pending_member_actions"], 1)
        self.assertFalse(result["sessions"]["own_application_api_configured"])
        self.assertEqual(result["pm2"]["status"], "ONLINE")
        self.assertEqual(result["telegram_requests"], 0)
        self.assertEqual(result["members_added"], 0)

    def test_secret_and_user_data_never_leak(self):
        output = json.dumps(self.build(), ensure_ascii=False)
        for secret in ("@secret_person", "@sensitive_person", "@secretGroup",
                       "Private Campaign Keyword", "Very Private Lookup Term",
                       "ABSOLUTE_SECRET_VALUE"):
            self.assertNotIn(secret, output)
        self.assertNotIn("auth_key", output)

    def test_offline_does_not_claim_online_health(self):
        result = self.build(pm2_records=None)
        self.assertEqual(result["status"], "OFFLINE_ONLY")
        result = self.build(pm2_records=[])
        self.assertEqual(result["status"], "NOT_LIVE_VERIFIED")
        result = self.build(pm2_records=[{"name": "telegram-robot-leads",
                                         "pm2_env": {"status": "stopped"}}])
        self.assertEqual(result["status"], "NOT_LIVE_VERIFIED")

    def test_stale_and_wrong_commit_are_not_live_verified(self):
        stale = self.build(now=self.now + 3600)
        self.assertEqual(stale["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")
        wrong = self.build(expected_sha="b" * 40)
        self.assertEqual(wrong["source"]["matches_expected"], False)
        self.assertEqual(wrong["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")

    def test_event_before_current_deployment_is_not_accepted(self):
        os.utime(self.marker, (self.now + 1, self.now + 1))
        result = self.build()
        self.assertEqual(result["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")

    def test_unverified_vault_never_claims_live(self):
        with patch.object(report, "inspect",
                          side_effect=report.ProbeBlocked("missing_credentials")):
            result = report.build_report(
                vault=self.vault, checkout=self.checkout,
                catalog_path=self.path, state_path=self.state,
                events_path=self.events, expected_sha=SHA,
                pm2_records=[{"name": "telegram-robot-leads",
                              "pm2_env": {"status": "online"}}],
                now=self.now)
        self.assertEqual(result["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")
        self.assertEqual(result["sessions"]["reason"], "missing_credentials")

    def test_hard_blocked_accounts_are_counted_without_identifiers(self):
        state = empty_state()
        state["accounts"]["2"]["blocked"] = True
        state["accounts"]["2"]["reason"] = "account_restricted"
        save_state(self.state, state)
        result = self.build()
        self.assertEqual(result["operation_state"]["accounts_blocked"], 1)
        self.assertNotIn("account_restricted", json.dumps(result))

    def test_malformed_state_is_not_interpreted_as_empty(self):
        self.state.write_text("invalid state", encoding="utf-8")
        self.state.chmod(0o600)
        result = self.build()
        self.assertEqual(result["operation_state"]["status"], "BLOCKED")
        self.assertEqual(result["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")

    def test_symlink_and_insecure_journal_are_refused(self):
        self.events.chmod(0o644)
        result = self.build()
        self.assertEqual(result["supervisor"]["status"], "BLOCKED")
        self.events.chmod(0o600)
        self.events.unlink()
        self.events.symlink_to(self.marker)
        result = self.build()
        self.assertEqual(result["supervisor"]["status"], "BLOCKED")

    def test_pm2_duplicate_process_is_not_certified(self):
        worker = {"name": "telegram-robot-leads", "pm2_env": {"status": "online"}}
        result = self.build(pm2_records=[worker, worker])
        self.assertEqual(result["pm2"]["status"], "DUPLICATE_WORKER")
        self.assertEqual(result["status"], "NOT_LIVE_VERIFIED")

    def test_runtime_block_is_redacted(self):
        self.events.write_text(json.dumps({
            "ts": int(self.now) - 1,
            "event": {"kind": "runtime_blocked", "reason": "FileNotFoundError",
                      "user": "@private_person"},
        }) + "\n", encoding="utf-8")
        result = self.build()
        self.assertEqual(result["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")
        self.assertEqual(result["supervisor"]["reason"], "FileNotFoundError")
        self.assertNotIn("@private_person", json.dumps(result))

    def test_source_marker_bad_permissions_not_trusted(self):
        self.marker.chmod(0o644)
        result = self.build()
        self.assertFalse(result["source"]["verified"])
        self.assertEqual(result["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")

    def test_missing_journal_and_catalog_report_uncertainty(self):
        self.events.unlink()
        self.path.unlink()
        result = self.build()
        self.assertEqual(result["supervisor"]["status"], "NO_EVENT_JOURNAL")
        self.assertEqual(result["public_discovery"]["status"], "NOT_RUN")
        self.assertEqual(result["status"], "PM2_ONLINE_DISCOVERY_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
