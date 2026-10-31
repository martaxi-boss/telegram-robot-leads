"""The existing worker reconciles its OWN Telegram accounts, no third-party users."""
import asyncio
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import safe_runtime
import operation_policy


class WorkerMembershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.state = self.root / "operation-state.json"
        self.account_calls = []
        self.events = []

    def run_cycle(self, *, failed_account=None):
        config = {
            "group": "@iptvpncode",
            "api_source": "private_app_credentials",
            "entries": [{"session": "one"}, {"session": "two"}],
        }

        async def fake_sync(_config, number, _connector):
            self.account_calls.append(number)
            if number == failed_account:
                raise safe_runtime.RegistryBlocked("test_registry_block")
            return {"status": "MEMBERSHIP_SCAN_COMPLETE",
                    "account": number, "confirmed": 1}

        def fake_registry():
            return {
                "accounts": {
                    "1": {"groups": {
                        "@publiciptv": {
                            "group_id": 123, "status": "MEMBER_CONFIRMED",
                            "verified_at": "2026-10-31",
                        }}},
                    "2": {"groups": {
                        "@euiptv": {
                            "group_id": 456, "status": "MEMBER_CONFIRMED",
                            "verified_at": "2026-10-31",
                        }}},
                },
            }

        async def fake_discover(*args, **kwargs):
            return {"status": "PUBLIC_DISCOVERY_ALREADY_ATTEMPTED_TODAY",
                    "new_public_groups": 0}

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {
                "TELEGRAM_PUBLIC_DISCOVERY_ENABLED": "1",
                "TELEGRAM_REGIONAL_PUBLIC_DISCOVERY_ENABLED": "1",
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
                safe_runtime, "discover_daily", new=fake_discover))
            stack.enter_context(patch.object(
                safe_runtime, "sync_one", new=fake_sync))
            stack.enter_context(patch.object(
                safe_runtime, "read_registry", side_effect=fake_registry))
            no_add = stack.enter_context(patch.object(
                safe_runtime, "_add_one", new_callable=AsyncMock))
            no_join = stack.enter_context(patch.object(
                safe_runtime, "_join_one", new_callable=AsyncMock))
            result = asyncio.run(safe_runtime._run_once_unlocked(self.vault))
            no_add.assert_not_awaited()
            no_join.assert_not_awaited()
        return result

    def test_both_accounts_verified_and_saved_without_contact_actions(self):
        result = self.run_cycle()
        self.assertEqual(self.account_calls, [1, 2])
        self.assertEqual(result["group_memberships"]["status"], "CHECKED")
        state = operation_policy.load_state(self.state)
        self.assertEqual(state["joined_groups"]["@publiciptv"]["account"], 1)
        self.assertEqual(state["joined_groups"]["@euiptv"]["account"], 2)
        self.assertEqual(state["joined_groups"]["@publiciptv"]["group_id"], 123)
        self.assertEqual(self.events[0]["group_memberships"]["accounts"]["1"]
                         ["status"], "MEMBERSHIP_SCAN_COMPLETE")
        self.assertEqual(result["member_actions"], [])

    def test_one_account_failure_does_not_mask_other_account(self):
        result = self.run_cycle(failed_account=1)
        self.assertEqual(self.account_calls, [1, 2])
        self.assertEqual(result["group_memberships"]["accounts"]["1"]
                         ["status"], "BLOCKED")
        self.assertEqual(result["group_memberships"]["accounts"]["2"]
                         ["confirmed"], 1)
        state = operation_policy.load_state(self.state)
        self.assertNotIn("@publiciptv", state["joined_groups"])
        self.assertIn("@euiptv", state["joined_groups"])


if __name__ == "__main__":
    unittest.main()
