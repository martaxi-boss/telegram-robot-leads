"""Offline certification for first-party growth: no live Telegram or other projects."""
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from operation_policy import (
    PolicyBlocked, PolicyDeferred, check_action, empty_state, load_state, save_state,
)
import organic_growth as growth
from safe_runtime import public_cycle_summary

TARGET = "@iptvpncode"
CHANNEL = "@ownedchannel"
NOW = datetime(2026, 10, 27, 15, 0, tzinfo=ZoneInfo("Europe/Lisbon")).timestamp()


def configured(**changes):
    model = {
        "schema": 1, "target_group": TARGET,
        "approve_join_requests": True,
        "owned_channel": CHANNEL, "publish_in_owned_channel": True,
        "publisher_account": 1,
    }
    model.update(changes)
    return model


class ModelConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        os.chmod(self.vault, 0o700)

    def write(self, value):
        path = self.vault / "growth_model.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_absent_model_never_enables_actions(self):
        self.assertIsNone(growth.read_model(self.vault, TARGET))
        self.assertEqual(growth.preview(self.vault, TARGET)["status"], "NOT_CONFIGURED")

    def test_readiness_does_not_leak_channel_handle(self):
        self.write(configured())
        ready = growth.preview(self.vault, TARGET)
        self.assertEqual(ready["status"], "CONFIGURED_NOT_ONLINE_VERIFIED")
        self.assertTrue(ready["join_request_approval"])
        self.assertTrue(ready["owned_channel_promotion"])
        self.assertNotIn(CHANNEL, json.dumps(ready))

    def test_invalid_flag_owner_or_target_is_rejected(self):
        for changes in (
            {"target_group": "@notmygroup"},
            {"owned_channel": TARGET},
            {"publisher_account": 0},
            {"approve_join_requests": "true"},
            {"publish_in_owned_channel": True, "owned_channel": None},
        ):
            self.write(configured(**changes))
            with self.subTest(changes=changes), self.assertRaises(growth.ProbeBlocked):
                growth.read_model(self.vault, TARGET)

    def test_insecure_or_symlink_model_is_rejected(self):
        path = self.write(configured())
        path.chmod(0o644)
        with self.assertRaises(growth.ProbeBlocked):
            growth.read_model(self.vault, TARGET)
        path.chmod(0o600)
        path.unlink()
        path.symlink_to(self.vault / "missing.json")
        with self.assertRaises(growth.ProbeBlocked):
            growth.read_model(self.vault, TARGET)


class FakeClient:
    def __init__(self, *, channel_owner=True, group_admin=True,
                 pending=None, response=None, send_result=None):
        self.channel_owner = channel_owner
        self.group_admin = group_admin
        self.pending = [] if pending is None else pending
        self.response = response if response is not None else SimpleNamespace(updates=[])
        self.send_result = send_result if send_result is not None else SimpleNamespace(id=777)
        self.calls = []
        self.messages = []
        self.disconnected = False

    def is_connected(self):
        return not self.disconnected

    async def disconnect(self):
        self.disconnected = True

    async def get_entity(self, handle):
        self.calls.append(("get_entity", handle))
        if handle == CHANNEL:
            return SimpleNamespace(
                broadcast=True, megagroup=False, creator=self.channel_owner,
                admin_rights=SimpleNamespace(post_messages=False),
            )
        if handle == TARGET:
            return SimpleNamespace(megagroup=True, broadcast=False)
        raise AssertionError("Unexpected source")

    async def get_permissions(self, entity, who):
        self.calls.append(("get_permissions", who))
        return SimpleNamespace(
            is_creator=self.group_admin, is_admin=self.group_admin,
            invite_users=self.group_admin,
        )

    async def send_message(self, channel, message, *, link_preview):
        self.calls.append(("send_message", link_preview))
        self.messages.append(message)
        return self.send_result

    async def __call__(self, request):
        name = type(request).__name__
        self.calls.append(("rpc", name))
        if isinstance(request, growth.GetChatInviteImportersRequest):
            importers = [
                SimpleNamespace(requested=True, user_id=user_id)
                for user_id in self.pending
            ]
            users = [
                SimpleNamespace(id=user_id, bot=False, deleted=False)
                for user_id in self.pending
            ]
            return SimpleNamespace(importers=importers, users=users)
        if isinstance(request, growth.HideChatJoinRequestRequest):
            return self.response
        raise AssertionError("Unexpected RPC type")


class OrganicGrowthTests(unittest.TestCase):
    def setUp(self):
        self.state = empty_state()
        self.snapshots = []
        self.config = {"group": TARGET, "api_source": "published_android_fallback"}

    def persist(self, state):
        # JSON copy proves the durable pre-request record was persisted.
        self.snapshots.append(json.loads(json.dumps(state)))

    def run(self, method, model, client, *, now=NOW):
        connector = AsyncMock(return_value=client)
        return asyncio.run(method(
            self.config, model, self.state, self.persist, connector, now=now,
        ))

    def test_disabled_models_never_open_a_client(self):
        connector = AsyncMock(side_effect=AssertionError("network not allowed"))
        async def task():
            owned = await growth.promote_owned_channel(
                self.config, configured(publish_in_owned_channel=False),
                self.state, self.persist, connector, now=NOW)
            request = await growth.approve_pending_join_request(
                self.config, configured(approve_join_requests=False),
                self.state, self.persist, connector, now=NOW)
            self.assertEqual(owned["status"], "DISABLED")
            self.assertEqual(request["status"], "DISABLED")
        asyncio.run(task())
        connector.assert_not_called()

    def test_owner_channel_promotes_link_once_per_day(self):
        model = configured()
        first = FakeClient(channel_owner=True)
        result = self.run(growth.promote_owned_channel, model, first)
        self.assertEqual(result["status"], "POSTED")
        self.assertEqual(len(first.messages), 1)
        self.assertIn("https://t.me/iptvpncode", first.messages[0])
        self.assertTrue(first.disconnected)
        self.assertEqual(self.snapshots[0]["owned_promotion"][CHANNEL]["status"], "preflight")
        self.assertEqual(self.snapshots[1]["owned_promotion"][CHANNEL]["status"], "pending")
        self.assertEqual(self.snapshots[-1]["owned_promotion"][CHANNEL]["status"], "posted")
        second = FakeClient(channel_owner=True)
        self.assertEqual(
            self.run(growth.promote_owned_channel, model, second)["status"],
            "ALREADY_POSTED_TODAY",
        )
        self.assertFalse(second.calls)

    def test_non_admin_channel_cannot_send_and_preflight_is_bounded(self):
        model = configured()
        first = FakeClient(channel_owner=False)
        with self.assertRaisesRegex(growth.ProbeBlocked, "post_rights"):
            self.run(growth.promote_owned_channel, model, first)
        self.assertEqual(first.messages, [])
        second = FakeClient(channel_owner=True)
        self.assertEqual(
            self.run(growth.promote_owned_channel, model, second)["status"],
            "PREFLIGHT_ALREADY_ATTEMPTED_TODAY",
        )
        self.assertEqual(second.calls, [])

    def test_channel_send_unknown_outcome_never_auto_replays(self):
        model = configured()
        first = FakeClient(send_result=SimpleNamespace(id=None))
        with self.assertRaisesRegex(PolicyBlocked, "manual_review"):
            self.run(growth.promote_owned_channel, model, first)
        self.assertEqual(
            self.state["owned_promotion"][CHANNEL]["status"], "pending"
        )
        second = FakeClient()
        self.assertEqual(
            self.run(growth.promote_owned_channel, model, second)["status"],
            "PENDING_MANUAL_RECONCILIATION",
        )
        self.assertEqual(second.calls, [])

    def test_join_request_from_own_group_gets_approved_once(self):
        model = configured()
        first = FakeClient(pending=[501])
        with patch.object(growth.utils, "get_input_user", return_value=object()) as conversion:
            result = self.run(growth.approve_pending_join_request, model, first)
        conversion.assert_called_once()
        self.assertEqual(result, {"status": "APPROVED_REQUEST", "approvals_accepted": 1})
        self.assertIn(("get_entity", TARGET), first.calls)
        self.assertNotIn(("get_entity", CHANNEL), first.calls)
        self.assertEqual(self.snapshots[1]["pending_join_requests"]["501"]["account"], 1)
        self.assertEqual(self.state["pending_join_requests"], {})
        self.assertEqual(self.state["approved_join_requests_done"]["501"]["status"], "approved")
        self.assertEqual(self.state["accounts"]["1"]["join_request_approvals"], 1)
        self.assertEqual(self.state["accounts"]["1"]["member_adds"], 0)
        self.assertTrue(first.disconnected)

    def test_no_pending_join_requests_is_a_real_zero_not_an_error(self):
        model = configured()
        client = FakeClient(pending=[])
        result = self.run(growth.approve_pending_join_request, model, client)
        self.assertEqual(result["status"], "NO_PENDING_REQUESTS")
        self.assertEqual(self.state["accounts"]["1"]["join_request_approvals"], 0)
        self.assertEqual(len([c for c in client.calls if c[0] == "rpc"]), 1)

    def test_missing_admin_rights_do_not_approve_or_repeat_immediately(self):
        model = configured()
        client = FakeClient(group_admin=False, pending=[501])
        with self.assertRaisesRegex(growth.ProbeBlocked, "admin_permission"):
            self.run(growth.approve_pending_join_request, model, client)
        other = FakeClient(pending=[501])
        self.assertEqual(
            self.run(growth.approve_pending_join_request, model, other)["status"],
            "NEXT_SCAN_NOT_DUE",
        )
        self.assertEqual(other.calls, [])

    def test_unknown_join_approval_is_pending_manual_not_retried(self):
        model = configured()
        client = FakeClient(pending=[501], response=SimpleNamespace(updates=None))
        with patch.object(growth.utils, "get_input_user", return_value=object()):
            with self.assertRaisesRegex(PolicyBlocked, "manual_review"):
                self.run(growth.approve_pending_join_request, model, client)
        self.assertIn("501", self.state["pending_join_requests"])
        self.assertEqual(self.state["accounts"]["1"]["join_request_approvals"], 0)
        second = FakeClient(pending=[501])
        self.assertEqual(
            self.run(growth.approve_pending_join_request, model, second)["status"],
            "PENDING_MANUAL_RECONCILIATION",
        )
        self.assertEqual(second.calls, [])

    def test_activity_quota_is_shared_with_existing_member_actions(self):
        self.state["accounts"]["1"]["join_request_approvals"] = 10
        with self.assertRaises(PolicyDeferred):
            check_action(self.state, 1, "member_add", now=NOW)
        self.state["accounts"]["1"]["join_request_approvals"] = 0
        self.state["accounts"]["1"]["member_adds"] = 10
        with self.assertRaises(PolicyDeferred):
            check_action(self.state, 1, "join_request_approval", now=NOW)

    def test_new_privacy_state_survives_midnight_without_rerequesting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.state["pending_join_requests"]["501"] = {"account": 1}
            self.state["approved_join_requests_done"]["502"] = {"status": "approved"}
            self.state["owned_promotion"][CHANNEL] = {
                "day": "2026-10-27", "status": "pending", "account": 1
            }
            save_state(path, self.state)
            with patch("operation_policy._today", return_value="2099-01-01"):
                loaded = load_state(path)
            self.assertIn("501", loaded["pending_join_requests"])
            self.assertIn("502", loaded["approved_join_requests_done"])
            self.assertEqual(loaded["owned_promotion"][CHANNEL]["status"], "pending")

    def test_public_summary_never_exposes_requester_ids_or_handles(self):
        record = {"status": "CYCLE", "organic_growth": {
            "join_requests": {"status": "APPROVED_REQUEST", "user_id": 501},
            "owned_promotion": {"status": "POSTED", "channel": CHANNEL}
        }}
        report = public_cycle_summary(record)
        self.assertEqual(report["join_requests_approved"], 1)
        self.assertEqual(report["owned_channel_posts"], 1)
        self.assertNotIn("501", json.dumps(report))
        self.assertNotIn(CHANNEL, json.dumps(report))


if __name__ == "__main__":
    unittest.main()
