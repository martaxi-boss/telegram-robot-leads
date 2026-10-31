"""Regression tests for aggregate reporting of explicitly authorized intake.

No Telegram network calls are made: identity and queue behavior are simulated.
"""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import operation_policy as policy
import safe_runtime


class ApprovedQueueVisibilityTests(unittest.TestCase):
    def test_queue_counts_are_anonymous_and_do_not_mutate_state(self):
        state = policy.empty_state()
        state["approved_users_done"]["@recorded"] = {
            "account": 1, "status": "added",
        }
        state["pending_member_actions"]["@uncertain"] = {
            "account": 2, "user_id": 987654,
        }
        state["approved_user_ids_done"]["987"] = {
            "account": 1, "status": "added",
        }
        state["approved_join_requests_done"]["987"] = {
            "account": 1, "status": "approved",
        }
        state["approved_join_requests_done"]["123"] = {
            "account": 2, "status": "approved",
        }
        original = json.dumps(state, sort_keys=True)
        snapshot = safe_runtime.approved_queue_snapshot(
            ["@recorded", "@uncertain", "@new"], state
        )
        self.assertEqual(snapshot, {
            "configured": 3, "waiting": 1, "recorded": 1,
            "uncertain": 1, "global_recorded_ids": 2,
        })
        self.assertEqual(json.dumps(state, sort_keys=True), original)
        self.assertNotIn("@", str(snapshot))
        self.assertNotIn("987654", str(snapshot))

        public = safe_runtime.public_cycle_summary({
            "approved_queue": snapshot, "member_actions": [],
        })
        self.assertEqual(public["approved_queue_configured"], 3)
        self.assertEqual(public["approved_queue_waiting"], 1)
        self.assertEqual(public["approved_queue_recorded"], 1)
        self.assertEqual(public["approved_queue_uncertain"], 1)
        self.assertEqual(public["approved_history_unique_ids"], 2)
        self.assertNotIn("@", str(public))

    def test_unknown_alias_never_bypasses_persisted_cross_account_history(self):
        state = policy.empty_state()
        state["approved_user_ids_done"]["43210"] = {
            "account": 1, "status": "added",
        }
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "operation-state.json"
            policy.save_state(p, state)
            recovered = policy.load_state(p)
            self.assertIn("43210", recovered["approved_user_ids_done"])

            class FakeClient:
                async def get_entity(self, _):
                    return object()

                async def get_input_entity(self, _):
                    return SimpleNamespace(user_id=43210)

                def is_connected(self):
                    return True

                async def disconnect(self):
                    return None

                def __call__(self, _):
                    raise AssertionError("repeated addition must never be sent")

            async def verify():
                with patch.object(safe_runtime, "check_action"), patch.object(
                    safe_runtime, "_connected_client",
                    new=AsyncMock(return_value=FakeClient()),
                ):
                    return await safe_runtime._add_one(
                        {"group": "@my_group"}, recovered,
                        "@changed_alias", 2,
                    )

            result = asyncio.run(verify())
            self.assertEqual(result, "already_recorded_identity")
            self.assertEqual(recovered["accounts"]["2"]["member_adds"], 0)
            self.assertEqual(
                recovered["approved_users_done"]["@changed_alias"]["status"],
                "already_recorded_identity",
            )
            # Leaving the destination group does not remove the old record.
            self.assertEqual(
                recovered["approved_user_ids_done"]["43210"]["status"],
                "added",
            )

    def test_missing_queue_snapshot_is_zero_and_non_integer_values_are_rejected(self):
        default = safe_runtime.public_cycle_summary({})
        self.assertEqual(default["approved_queue_configured"], 0)
        self.assertEqual(default["approved_history_unique_ids"], 0)
        report = safe_runtime.public_cycle_summary({
            "approved_queue": {
                "configured": True,
                "waiting": -20,
                "recorded": "@name",
                "uncertain": 4,
                "global_recorded_ids": None,
            }
        })
        self.assertEqual(report["approved_queue_configured"], 0)
        self.assertEqual(report["approved_queue_waiting"], 0)
        self.assertEqual(report["approved_queue_recorded"], 0)
        self.assertEqual(report["approved_queue_uncertain"], 4)
        self.assertEqual(report["approved_history_unique_ids"], 0)


if __name__ == "__main__":
    unittest.main()
