"""Offline integration tests for bounded dual-account regional discovery."""
import asyncio
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import safe_runtime
import operation_policy


class RegionalWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.state = self.root / "state.json"
        self.calls = []
        self.events = []

    def _run(self, discover, catalog=None):
        config = {
            "group": "@iptvpncode", "api_source": "private_app_credentials",
            "entries": [{"session": "first"}, {"session": "second"}],
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {
                "TELEGRAM_PUBLIC_DISCOVERY_ENABLED": "1",
                "TELEGRAM_REGIONAL_PUBLIC_DISCOVERY_ENABLED": "1",
                "TELEGRAM_TZ": "Europe/Lisbon",
            }))
            stack.enter_context(patch.object(
                safe_runtime, "inspect", return_value=config))
            stack.enter_context(patch.object(
                safe_runtime, "load_group_allowlist", return_value=[]))
            stack.enter_context(patch.object(
                safe_runtime, "load_approved_users", return_value=[]))
            stack.enter_context(patch.object(
                safe_runtime, "read_model", return_value=None))
            stack.enter_context(patch.object(
                safe_runtime, "_state_path", return_value=self.state))
            stack.enter_context(patch.object(
                safe_runtime, "append_supervisor_event",
                side_effect=self.events.append))
            stack.enter_context(patch.object(
                safe_runtime, "discover_daily", new=discover))
            stack.enter_context(patch.object(
                safe_runtime, "read_catalog",
                return_value={"groups": catalog or {}}))
            no_join = stack.enter_context(patch.object(
                safe_runtime, "_join_one", new_callable=AsyncMock))
            no_add = stack.enter_context(patch.object(
                safe_runtime, "_add_one", new_callable=AsyncMock))
            result = asyncio.run(safe_runtime._run_once_unlocked(self.vault))
            self.join_calls = [(c.args[2], c.args[3])
                               for c in no_join.await_args_list]
            if not catalog:
                no_join.assert_not_awaited()
            no_add.assert_not_awaited()
        return result

    def test_both_sessions_are_scheduled_in_correct_region(self):
        async def discover(config, vault, *, account_number, region):
            self.calls.append((account_number, region))
            return {"status": "PUBLIC_DISCOVERY_COMPLETE",
                    "new_public_groups": 1}

        result = self._run(discover)
        self.assertEqual(self.calls, [(1, "PT_ES"), (2, "EU_OTHER")])
        self.assertEqual(result["public_discovery"]["new_public_groups"], 2)
        self.assertEqual(result["public_discovery"]["status"],
                         "PUBLIC_DISCOVERY_COMPLETE")
        self.assertEqual(result["member_actions"], [])
        self.assertEqual(self.events[0]["kind"], "cycle")

    def test_discovered_group_can_be_joined_by_both_accounts(self):
        async def discover(config, vault, *, account_number, region):
            return {"status": "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
                    "new_public_groups": 0}

        result = self._run(discover, catalog={
            "@publiciptv": {"matched_regions": ["PT_ES", "EU_OTHER"]},
        })
        self.assertEqual(self.join_calls, [
            ("@publiciptv", 1), ("@publiciptv", 2),
        ])
        self.assertEqual(len(result["group_actions"]), 2)

    def test_rate_limit_stops_only_affected_account(self):
        async def discover(config, vault, *, account_number, region):
            self.calls.append((account_number, region))
            if account_number == 1:
                raise safe_runtime.DiscoveryBlocked(
                    "telegram_search_rate_or_account_restriction")
            return {"status": "PUBLIC_DISCOVERY_COMPLETE",
                    "new_public_groups": 0}

        result = self._run(discover)
        self.assertEqual(self.calls, [(1, "PT_ES"), (2, "EU_OTHER")])
        self.assertEqual(result["public_discovery"]["regional_accounts"]["1"]["status"],
                         "BLOCKED")
        self.assertTrue(operation_policy.load_state(self.state)["accounts"]["1"]["blocked"])
        self.assertFalse(operation_policy.load_state(self.state)["accounts"]["2"]["blocked"])

    def test_preblocked_account_does_not_cause_region_reassignment(self):
        state = operation_policy.empty_state()
        operation_policy.block_account(state, 1, "PeerFloodError")
        operation_policy.save_state(self.state, state)

        async def discover(config, vault, *, account_number, region):
            self.calls.append((account_number, region))
            return {"status": "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
                    "new_public_groups": 0}

        result = self._run(discover)
        self.assertEqual(self.calls, [(2, "EU_OTHER")])
        self.assertEqual(result["public_discovery"]["status"],
                         "REGIONAL_DISCOVERY_PARTIAL")
        self.assertEqual(result["public_discovery"]["regional_accounts"]["1"]["reason"],
                         "account_hard_stop")


if __name__ == "__main__":
    unittest.main()
