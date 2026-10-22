"""Offline regression tests for durable account hard stops and state privacy.

No Telegram API calls, credentials, sessions or production filesystem access.
"""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import operation_policy as policy
import safe_runtime


class DurableStatePrivacyTests(unittest.TestCase):
    def test_private_state_round_trips_existing_counters(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "operation-state.json"
            state = policy.empty_state()
            state["accounts"]["1"]["member_adds"] = 3
            state["pending_member_actions"]["@someone"] = {
                "account": 1, "user_id": 123456
            }
            policy.save_state(path, state)
            restored = policy.load_state(path)
            self.assertEqual(restored["accounts"]["1"]["member_adds"], 3)
            self.assertIn("@someone", restored["pending_member_actions"])

    def test_existing_publicly_readable_state_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "operation-state.json"
            policy.save_state(path, policy.empty_state())
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(
                policy.PolicyBlocked, "state_permissions_or_size_invalid"
            ):
                policy.load_state(path)

    def test_block_survives_day_change(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "operation-state.json"
            state = policy.empty_state()
            policy.block_account(state, 1, "PeerFloodError")
            policy.save_state(path, state)
            with patch.object(policy, "_today", return_value="2099-10-24"):
                restored = policy.load_state(path)
            self.assertTrue(restored["accounts"]["1"]["blocked"])


class PublicDiscoveryHardStopTests(unittest.TestCase):
    def _cycle(self, blocked):
        state = policy.empty_state()
        if blocked:
            policy.block_account(state, 1, "PeerFloodError")
        config = {
            "api_source": "private_app_credentials",
            "group": "@iptvpncode",
            "entries": [{}, {}],
        }
        with (
            patch.dict(os.environ, {"TELEGRAM_PUBLIC_DISCOVERY_ENABLED": "1"}),
            patch.object(safe_runtime, "inspect", return_value=config),
            patch.object(safe_runtime, "load_group_allowlist", return_value=[]),
            patch.object(safe_runtime, "load_approved_users", return_value=[]),
            patch.object(safe_runtime, "load_state", return_value=state),
            patch.object(safe_runtime, "save_state"),
            patch.object(safe_runtime, "append_supervisor_event"),
            patch.object(safe_runtime, "discover_daily", new_callable=AsyncMock) as discovery,
        ):
            discovery.return_value = {"status": "PUBLIC_DISCOVERY_COMPLETE"}
            result = asyncio.run(safe_runtime._run_once_unlocked(Path("/no-network")))
            return result, discovery.await_count

    def test_blocked_account_cannot_search_again(self):
        result, attempted = self._cycle(blocked=True)
        self.assertEqual(attempted, 0)
        self.assertEqual(result["public_discovery"], {
            "status": "BLOCKED",
            "reason": "account_1_hard_stop",
        })
        self.assertEqual(result["member_actions"], [])
        self.assertEqual(result["group_actions"], [])

    def test_unblocked_account_keeps_existing_discovery(self):
        result, attempted = self._cycle(blocked=False)
        self.assertEqual(attempted, 1)
        self.assertEqual(result["public_discovery"]["status"],
                         "PUBLIC_DISCOVERY_COMPLETE")


if __name__ == "__main__":
    unittest.main()
