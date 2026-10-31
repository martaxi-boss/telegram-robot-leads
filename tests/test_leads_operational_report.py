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

    def test_shared_processed_identity_counts_are_distinct_and_private(self):
        state = empty_state()
        state["approved_user_ids_done"]["123456"] = {
            "account": 1, "status": "added",
        }
        state["approved_join_requests_done"]["123456"] = {
            "account": 2, "status": "approved",
        }
        state["approved_join_requests_done"]["654321"] = {
            "account": 2, "status": "approved",
        }
        state["pending_member_ids"]["999999"] = {
            "account": 1, "username": "@somebody",
        }
        save_state(self.state, state)
        result = self.build()
        record = result["operation_state"]
        self.assertEqual(record["distinct_processed_member_identities"], 2)
        self.assertEqual(record["processed_authorised_add_identity_records"], 1)
        self.assertEqual(record["processed_voluntary_request_identity_records"], 2)
        self.assertEqual(record["pending_identity_reconciliation"], 1)
        self.assertNotIn("CURRENT_MEMBER_IDENTITY_HISTORY_EMPTY",
                         result["readiness_indicators"])
        public = json.dumps(result)
        for user_id in ("123456", "654321", "999999"):
            self.assertNotIn(user_id, public)

    def test_zero_identity_history_is_a_reported_readiness_gap(self):
        result = self.build()
        self.assertEqual(result["operation_state"]["distinct_processed_member_identities"], 0)
        self.assertIn("CURRENT_MEMBER_IDENTITY_HISTORY_EMPTY",
                      result["readiness_indicators"])

    def test_secret_and_user_data_never_leak(self):
        output = json.dumps(self.build(), ensure_ascii=False)
        for secret in ("@secret_person", "@sensitive_person", "@secretGroup",
                       "Private Campaign Keyword", "Very Private Lookup Term",
                       "ABSOLUTE_SECRET_VALUE"):
            self.assertNotIn(secret, output)
        self.assertNotIn("auth_key", output)

    def test_public_search_can_work_without_any_approved_users_or_state(self):
        # The runtime only writes action state when it attempts authorized
        # joins/adds; an empty queue must not invalidate real search evidence.
        self.state.unlink()
        result = self.build()
        self.assertEqual(result["operation_state"]["status"], "NOT_CREATED")
        self.assertEqual(result["status"], "LIVE_PUBLIC_DISCOVERY_OBSERVED")
        self.assertEqual(result["supervisor"]["public_discovery_status"],
                         "PUBLIC_DISCOVERY_COMPLETE")

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


    def test_action_queue_explains_empty_member_activity_without_names(self):
        result = self.build()
        self.assertEqual(result["action_queue"]["status"], "READABLE")
        self.assertEqual(result["action_queue"]["approved_username_entries"], 0)
        self.assertEqual(result["action_queue"]["member_queue_status"], "EMPTY")

        approved = self.vault / "approved_users.txt"
        approved.write_text(
            "@PrivateAlpha|APPROVED\n@PrivateBravo|CONSENTED\n",
            encoding="utf-8",
        )
        approved.chmod(0o600)
        allowlist = self.vault / "group_allowlist.txt"
        allowlist.write_text("@PrivateGroup\n", encoding="utf-8")
        allowlist.chmod(0o600)
        result = self.build()
        self.assertEqual(result["action_queue"]["approved_username_entries"], 2)
        self.assertEqual(result["action_queue"]["allowlisted_group_entries"], 1)
        self.assertEqual(
            result["action_queue"]["member_queue_status"],
            "OPERATOR_ENTRIES_NOT_ONLINE_VERIFIED",
        )
        output = json.dumps(result)
        for handle in ("@PrivateAlpha", "@PrivateBravo", "@PrivateGroup"):
            self.assertNotIn(handle, output)

    def test_invalid_action_queue_permission_does_not_leak_usernames(self):
        approved = self.vault / "approved_users.txt"
        approved.write_text("@PrivateAlpha|APPROVED\n", encoding="utf-8")
        approved.chmod(0o644)
        result = self.build()
        self.assertEqual(result["action_queue"]["status"], "BLOCKED")
        self.assertNotIn("@PrivateAlpha", json.dumps(result))

    def test_report_cli_skips_pm2_by_default(self):
        import io
        with patch.object(report, "read_pm2", side_effect=AssertionError("PM2 invoked")), \
             patch.object(report, "build_report", return_value={"status": "OFFLINE_ONLY"}) as build, \
             patch("sys.argv", ["leads_operational_report.py"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(report.main(), 0)
        self.assertIsNone(build.call_args.kwargs["pm2_records"])

    def test_report_cli_queries_pm2_only_when_explicitly_requested(self):
        import io
        with patch.object(report, "read_pm2", return_value=([], None)) as query, \
             patch.object(report, "build_report", return_value={"status": "NOT_LIVE_VERIFIED"}), \
             patch("sys.argv", ["leads_operational_report.py", "--with-pm2"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(report.main(), 0)
        query.assert_called_once_with()

    def test_growth_readiness_explains_why_zero_does_not_mean_a_network_error(self):
        result = self.build(expected_sha="b" * 40)
        self.assertEqual(result["organic_growth_model"]["status"], "NOT_CONFIGURED")
        self.assertIn(
            "NO_APPROVED_USERS_IN_DIRECT_ADD_QUEUE", result["readiness_indicators"]
        )
        self.assertIn(
            "ORGANIC_GROWTH_MODEL_NOT_CONFIGURED", result["readiness_indicators"]
        )
        self.assertIn(
            "PRIVATE_APPLICATION_CREDENTIALS_NOT_CONFIGURED", result["readiness_indicators"]
        )
        self.assertIn(
            "INSTALLED_SOURCE_DIFFERS_FROM_EXPECTED", result["readiness_indicators"]
        )

    def test_growth_model_config_readiness_does_not_leak_channel_handle(self):
        config = self.vault / "growth_model.json"
        config.write_text(json.dumps({
            "schema": 1,
            "target_group": "@iptvpncode",
            "approve_join_requests": True,
            "owned_channel": "@PrivateOwnedChannel",
            "publish_in_owned_channel": True,
            "publisher_account": 1,
        }), encoding="utf-8")
        config.chmod(0o600)
        result = self.build()
        self.assertEqual(
            result["organic_growth_model"]["status"],
            "CONFIGURED_NOT_ONLINE_VERIFIED",
        )
        self.assertNotIn("@PrivateOwnedChannel", json.dumps(result))
        self.assertNotIn(
            "ORGANIC_GROWTH_MODEL_NOT_CONFIGURED", result["readiness_indicators"]
        )

    def test_supervisor_growth_counters_are_readonly_and_redacted(self):
        self.events.write_text(json.dumps({
            "ts": int(self.now) - 2,
            "event": {
                "kind": "cycle",
                "group_actions": [],
                "member_actions": [],
                "blocked": [],
                "organic_growth": {
                    "join_requests": {
                        "status": "APPROVED_REQUEST", "user_id": 222222
                    },
                    "owned_promotion": {
                        "status": "POSTED", "channel": "@SecretOwnedChannel"
                    },
                },
            },
        }) + "\n", encoding="utf-8")
        outcome = self.build()
        self.assertEqual(outcome["supervisor"]["approvals_in_last_cycle"], 1)
        self.assertEqual(outcome["supervisor"]["owned_posts_in_last_cycle"], 1)
        self.assertEqual(outcome["supervisor"]["join_request_status"], "APPROVED_REQUEST")
        self.assertNotIn("222222", json.dumps(outcome))
        self.assertNotIn("@SecretOwnedChannel", json.dumps(outcome))


if __name__ == "__main__":
    unittest.main()
