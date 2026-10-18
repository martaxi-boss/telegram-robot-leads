from pathlib import Path
import os
import json
import asyncio
import fcntl
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import operation_policy as policy
import safe_runtime


class OperationPolicyTests(unittest.TestCase):
    def test_per_account_group_limit_is_one(self):
        state = policy.empty_state()
        state["accounts"]["1"]["group_joins"] = 1
        with self.assertRaises(policy.PolicyDeferred):
            policy.check_action(state, 1, "group_join", now=10000)

    def test_project_group_limit_is_two(self):
        state = policy.empty_state()
        state["accounts"]["1"]["group_joins"] = 1
        state["accounts"]["2"]["group_joins"] = 1
        with self.assertRaises(policy.PolicyDeferred):
            policy.check_action(state, 1, "group_join", now=10000)

    def test_per_account_member_limit_is_ten(self):
        state = policy.empty_state()
        state["accounts"]["1"]["member_adds"] = 10
        with self.assertRaises(policy.PolicyDeferred):
            policy.check_action(state, 1, "member_add", now=10000)

    def test_project_member_limit_is_twenty(self):
        state = policy.empty_state()
        state["accounts"]["1"]["member_adds"] = 10
        state["accounts"]["2"]["member_adds"] = 10
        with self.assertRaises(policy.PolicyDeferred):
            policy.check_action(state, 1, "member_add", now=10000)

    def test_fixed_interval_not_randomized(self):
        state = policy.empty_state()
        state["accounts"]["1"]["last_action"] = 1000
        with self.assertRaises(policy.PolicyDeferred):
            policy.check_action(state, 1, "member_add", now=1001)
        policy.check_action(
            state,
            1,
            "member_add",
            now=1000 + policy.MIN_INTERVAL_SECONDS,
        )

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(policy.PolicyBlocked):
                policy.load_state(path)

    def test_blocked_account_cannot_continue(self):
        state = policy.empty_state()
        policy.block_account(state, 2, "PeerFloodError")
        with self.assertRaises(policy.PolicyBlocked):
            policy.check_action(state, 2, "group_join", now=10000)

    def test_malformed_usage_counters_block(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "operation-state.json"
            state = policy.empty_state()
            state["accounts"]["1"]["member_adds"] = "not-a-number"
            path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(policy.PolicyBlocked):
                policy.load_state(path)

    def test_pending_outcomes_and_flood_block_survive_midnight(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "operation-state.json"
            state = policy.empty_state()
            policy.block_account(state, 1, "PeerFloodError")
            state["pending_group_actions"]["@examplegroup"] = {"account": 1}
            state["pending_member_actions"]["@exampleuser"] = {"account": 2}
            policy.save_state(path, state)
            with patch.object(policy, "_today", return_value="2099-01-02"):
                restored = policy.load_state(path)
            self.assertTrue(restored["accounts"]["1"]["blocked"])
            self.assertIn("@examplegroup", restored["pending_group_actions"])
            self.assertIn("@exampleuser", restored["pending_member_actions"])

    def test_non_integer_counter_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            for invalid in (1.5, float("nan"), float("inf"), True):
                state = policy.empty_state()
                state["accounts"]["1"]["member_adds"] = invalid
                path.write_text(json.dumps(state), encoding="utf-8")
                with self.assertRaises(policy.PolicyBlocked):
                    policy.load_state(path)

    def test_symlinked_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "real.json"
            policy.save_state(source, policy.empty_state())
            alias = Path(root) / "operation-state.json"
            alias.symlink_to(source)
            with self.assertRaises(policy.PolicyBlocked):
                policy.load_state(alias)


class SafeRuntimeInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        os.chmod(self.vault, 0o700)

    def _write_private(self, name, content):
        path = self.vault / name
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def test_group_allowlist_is_explicit_and_deduplicated(self):
        self._write_private(
            "group_allowlist.txt",
            "# approved\n@examplegroup\nExampleGroup\n",
        )
        self.assertEqual(
            safe_runtime.load_group_allowlist(self.vault),
            ["@examplegroup"],
        )

    def test_member_requires_explicit_approval_marker(self):
        self._write_private("approved_users.txt", "@someone\n")
        with self.assertRaisesRegex(
            safe_runtime.ProbeBlocked, "explicit_marker"
        ):
            safe_runtime.load_approved_users(self.vault)

    def test_member_approved_marker_is_accepted(self):
        self._write_private(
            "approved_users.txt",
            "@someone|APPROVED\n@another|CONSENTED\n",
        )
        self.assertEqual(
            safe_runtime.load_approved_users(self.vault),
            ["@someone", "@another"],
        )

    def test_account_assignment_is_stable(self):
        first = safe_runtime.assigned_account("@ExampleGroup")
        second = safe_runtime.assigned_account("@examplegroup")
        self.assertEqual(first, second)
        self.assertIn(first, (1, 2))

    def test_second_instance_cannot_enter_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            lock = Path(root) / "state.json.lock"
            with open(lock, "w", encoding="utf-8") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(safe_runtime, "_state_path", return_value=path), patch.object(
                    safe_runtime, "_run_once_unlocked", side_effect=AssertionError("should never run")
                ):
                    with self.assertRaisesRegex(policy.PolicyBlocked, "another_runtime_active"):
                        asyncio.run(safe_runtime.run_once(self.vault))

    def test_unresolved_outcome_is_never_auto_replayed(self):
        async def check():
            state = policy.empty_state()
            state["pending_group_actions"]["@examplegroup"] = {"account": 1}
            state["pending_member_actions"]["@exampleuser"] = {"account": 2}
            with patch.object(safe_runtime, "_connected_client",
                              side_effect=AssertionError("network must not run")):
                with self.assertRaisesRegex(policy.PolicyBlocked, "outcome_unknown"):
                    await safe_runtime._join_one({}, state, "@examplegroup", 1)
                with self.assertRaisesRegex(policy.PolicyBlocked, "outcome_unknown"):
                    await safe_runtime._add_one({"group": "@examplegroup"}, state,
                                                "@exampleuser", 2)
        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
