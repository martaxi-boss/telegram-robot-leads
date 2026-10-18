from pathlib import Path
import os
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
