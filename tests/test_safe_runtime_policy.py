from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import os
import json
import asyncio
import fcntl
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

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
            now=12 * 3600,
        )

    def test_member_capacity_is_spread_across_the_day(self):
        zone = ZoneInfo("Europe/Lisbon")
        def ts(h, m):
            return datetime(2026, 1, 1, h, m, tzinfo=zone).timestamp()

        self.assertEqual(policy.member_time_budget(1, now=ts(7, 59)), 0)
        self.assertEqual(policy.member_time_budget(1, now=ts(8, 0)), 1)
        self.assertEqual(policy.member_time_budget(2, now=ts(8, 0)), 0)
        self.assertEqual(policy.member_time_budget(2, now=ts(8, 42)), 1)
        self.assertLess(policy.member_time_budget(1, now=ts(12, 0)), 10)
        self.assertLess(policy.member_time_budget(2, now=ts(12, 0)), 10)
        self.assertEqual(policy.member_time_budget(1, now=ts(22, 0)), 10)
        self.assertEqual(policy.member_time_budget(2, now=ts(22, 0)), 10)

    def test_second_add_is_deferred_until_next_daily_position(self):
        zone = ZoneInfo("Europe/Lisbon")
        state = policy.empty_state()
        state["accounts"]["1"]["member_adds"] = 1
        at_open = datetime(2026, 1, 1, 8, 20, tzinfo=zone).timestamp()
        with self.assertRaisesRegex(policy.PolicyDeferred, "member_day_distribution"):
            policy.check_action(state, 1, "member_add", now=at_open)

    def test_member_add_only_within_portugal_daytime(self):
        state = policy.empty_state()
        before = datetime(2026, 1, 1, 7, 59, tzinfo=ZoneInfo("Europe/Lisbon"))
        opening = datetime(2026, 1, 1, 8, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        closing = datetime(2026, 1, 1, 22, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        with self.assertRaisesRegex(policy.PolicyDeferred, "member_activity_window"):
            policy.check_action(state, 1, "member_add", now=before.timestamp())
        policy.check_action(state, 1, "member_add", now=opening.timestamp())
        with self.assertRaisesRegex(policy.PolicyDeferred, "member_activity_window"):
            policy.check_action(state, 1, "member_add", now=closing.timestamp())

    def test_member_id_dedupe_survives_midnight(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = policy.empty_state()
            state["approved_user_ids_done"]["123456"] = {
                "account": 1, "status": "added"
            }
            state["pending_member_ids"]["654321"] = {
                "account": 2, "username": "@someone"
            }
            policy.save_state(path, state)
            with patch.object(policy, "_today", return_value="2099-02-02"):
                restored = policy.load_state(path)
            self.assertIn("123456", restored["approved_user_ids_done"])
            self.assertIn("654321", restored["pending_member_ids"])

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

    def test_new_group_uses_account_with_available_daily_slot(self):
        state = policy.empty_state()
        state["accounts"]["1"]["group_joins"] = 1
        self.assertEqual(
            safe_runtime.assigned_group_account(state, "@freshgroup"), 2
        )
        state["accounts"]["1"]["group_joins"] = 0
        state["accounts"]["2"]["group_joins"] = 1
        self.assertEqual(
            safe_runtime.assigned_group_account(state, "@freshgroup"), 1
        )

    def test_group_pending_or_joined_account_is_not_reassigned(self):
        state = policy.empty_state()
        state["accounts"]["1"]["group_joins"] = 1
        state["pending_group_actions"]["@freshgroup"] = {"account": 1}
        self.assertEqual(
            safe_runtime.assigned_group_account(state, "@FRESHGROUP"), 1
        )
        del state["pending_group_actions"]["@freshgroup"]
        state["joined_groups"]["@freshgroup"] = {"account": 1}
        self.assertEqual(
            safe_runtime.assigned_group_account(state, "@freshgroup"), 1
        )

    def test_equal_available_daily_slots_keep_stable_tiebreak(self):
        state = policy.empty_state()
        self.assertEqual(
            safe_runtime.assigned_group_account(state, "@freshgroup"),
            safe_runtime.assigned_account("@freshgroup"),
        )

    def test_same_consented_user_id_from_other_account_is_not_added_again(self):
        class FakeClient:
            async def get_entity(self, _):
                return object()
            async def get_input_entity(self, _):
                return SimpleNamespace(user_id=123456)
            def is_connected(self):
                return True
            async def disconnect(self):
                pass
            def __call__(self, _):
                raise AssertionError("duplicate must never result in an add request")

        async def check():
            state = policy.empty_state()
            state["approved_user_ids_done"]["123456"] = {
                "account": 1, "status": "added"
            }
            with patch.object(safe_runtime, "check_action"), patch.object(
                safe_runtime, "_connected_client",
                new=AsyncMock(return_value=FakeClient())
            ):
                result = await safe_runtime._add_one(
                    {"group": "@targetgroup"}, state, "@renamed_user", 2
                )
            self.assertEqual(result, "already_recorded_identity")
            self.assertEqual(
                state["approved_users_done"]["@renamed_user"]["status"],
                "already_recorded_identity",
            )
            self.assertEqual(state["accounts"]["2"]["member_adds"], 0)
        asyncio.run(check())

    def test_previously_approved_join_request_never_causes_direct_add(self):
        class FakeClient:
            async def get_entity(self, _):
                return object()
            async def get_input_entity(self, _):
                return SimpleNamespace(user_id=123456)
            def is_connected(self):
                return True
            async def disconnect(self):
                pass
            def __call__(self, _):
                raise AssertionError("no repeat call may reach Telegram")
        async def check():
            state = policy.empty_state()
            state["approved_join_requests_done"]["123456"] = {
                "account": 1, "status": "approved",
            }
            with patch.object(safe_runtime, "check_action"), patch.object(
                safe_runtime, "_connected_client",
                new=AsyncMock(return_value=FakeClient()),
            ):
                result = await safe_runtime._add_one(
                    {"group": "@targetgroup"}, state, "@different_alias", 2,
                )
            self.assertEqual(result, "already_recorded_identity")
            self.assertEqual(state["accounts"]["2"]["member_adds"], 0)
        asyncio.run(check())

    def test_ambiguous_same_id_pending_is_never_retried(self):
        class FakeClient:
            async def get_entity(self, _):
                return object()
            async def get_input_entity(self, _):
                return SimpleNamespace(user_id=123456)
            def is_connected(self):
                return True
            async def disconnect(self):
                pass
            def __call__(self, _):
                raise AssertionError("no network addition may occur")

        async def check():
            state = policy.empty_state()
            state["pending_member_ids"]["123456"] = {
                "account": 1, "username": "@original"
            }
            with patch.object(safe_runtime, "check_action"), patch.object(
                safe_runtime, "_connected_client",
                new=AsyncMock(return_value=FakeClient())
            ):
                with self.assertRaisesRegex(policy.PolicyBlocked, "outcome_unknown"):
                    await safe_runtime._add_one(
                        {"group": "@targetgroup"}, state, "@new_alias", 2
                    )
        asyncio.run(check())

    def test_existing_verified_api_source_is_not_artificially_blocked(self):
        async def check():
            state = policy.empty_state()
            with tempfile.TemporaryDirectory() as root:
                vault = Path(root)
                journal = Path(root) / "events.jsonl"
                with patch.object(
                    safe_runtime,
                    "inspect",
                    return_value={"api_source": "published_android_fallback"},
                ), patch.object(
                    safe_runtime, "load_group_allowlist", return_value=[]
                ), patch.object(
                    safe_runtime, "load_approved_users", return_value=[]
                ), patch.object(
                    safe_runtime, "_state_path", return_value=Path(root) / "state.json"
                ), patch.object(
                    safe_runtime, "_event_journal_path", return_value=journal
                ):
                    result = await safe_runtime._run_once_unlocked(vault)
                self.assertEqual(result["group_actions"], [])
                self.assertEqual(result["member_actions"], [])
                event = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(event["event"]["api_source"], "published_android_fallback")
                self.assertEqual(event["event"]["kind"], "cycle")
        asyncio.run(check())

    def test_supervisor_event_journal_is_private_and_append_only(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "events.jsonl"
            with patch.object(safe_runtime, "_event_journal_path", return_value=path):
                safe_runtime.append_supervisor_event({"kind": "one"})
                safe_runtime.append_supervisor_event({"kind": "two"})
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["event"]["kind"] for row in rows], ["one", "two"])
            self.assertEqual(path.stat().st_mode & 0o077, 0)

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
