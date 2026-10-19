"""Offline proof of the actual Telegram invite response contract.

An HTTP/MTProto success does not guarantee a member was added. Telegram's
messages.InvitedUsers carries missing_invitees for unsuccessful invitations.
Tests use a fake client and do not connect Telegram or touch the production VPS.
"""
from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import operation_policy as policy
import safe_runtime


USER_ID = 987654321


class FakeClient:
    def __init__(self, result, journal_path):
        self.result = result
        self.journal_path = journal_path
        self.calls = 0
        self.disconnected = False

    async def get_entity(self, group):
        assert group == "@targetgroup"
        return SimpleNamespace(id=9)

    async def get_input_entity(self, username):
        assert username == "@ConsentUser"
        return SimpleNamespace(user_id=USER_ID)

    async def __call__(self, request):
        self.calls += 1
        # The attempted add is written to the journal BEFORE the API call.
        pending = json.loads(self.journal_path.read_text(encoding="utf-8"))
        assert "@consentuser" in pending["pending_member_actions"]
        assert str(USER_ID) in pending["pending_member_ids"]
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def is_connected(self):
        return not self.disconnected

    async def disconnect(self):
        self.disconnected = True


class VerifiedInviteOutcomesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.journal = Path(self.folder.name) / "operation-state.json"

    async def attempt(self, result):
        state = policy.empty_state()
        fake = FakeClient(result, self.journal)
        with (
            patch.object(safe_runtime, "_connected_client",
                         new=AsyncMock(return_value=fake)),
            patch.object(safe_runtime, "_state_path", return_value=self.journal),
            patch.object(safe_runtime, "check_action", return_value=None),
        ):
            try:
                status = await safe_runtime._add_one(
                    {"group": "@targetgroup"}, state, "@ConsentUser", 1
                )
                return state, fake, status, None
            except Exception as exc:
                return state, fake, None, exc

    def test_missing_invitee_is_not_falsely_reported_as_added(self):
        outcome = SimpleNamespace(missing_invitees=[
            SimpleNamespace(user_id=USER_ID, premium_would_allow_invite=True)
        ])
        state, fake, result, exc = asyncio.run(self.attempt(outcome))
        self.assertIsNone(exc)
        self.assertEqual(result, "not_addable")
        self.assertEqual(state["approved_users_done"]["@consentuser"]["status"],
                         "not_addable")
        self.assertEqual(state["approved_users_done"]["@consentuser"]["reason"],
                         "TelegramMissingInvitee")
        self.assertEqual(state["approved_user_ids_done"][str(USER_ID)]["status"],
                         "not_addable")
        self.assertEqual(state["accounts"]["1"]["member_adds"], 0)
        self.assertFalse(state["pending_member_actions"])
        self.assertFalse(state["pending_member_ids"])
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.disconnected)

    def test_verified_success_with_no_missing_invitees_is_counted_once(self):
        state, fake, result, exc = asyncio.run(
            self.attempt(SimpleNamespace(missing_invitees=[]))
        )
        self.assertIsNone(exc)
        self.assertEqual(result, "added")
        self.assertEqual(state["accounts"]["1"]["member_adds"], 1)
        self.assertFalse(state["pending_member_actions"])
        self.assertFalse(state["pending_member_ids"])
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.disconnected)

    def test_unknown_response_is_never_counted_and_stays_pending(self):
        state, fake, result, exc = asyncio.run(self.attempt(
            SimpleNamespace(updates=[])
        ))
        self.assertIsNone(result)
        self.assertIsInstance(exc, policy.PolicyBlocked)
        self.assertIn("manual_reconciliation_required", str(exc))
        self.assertEqual(state["accounts"]["1"]["member_adds"], 0)
        self.assertIn("@consentuser", state["pending_member_actions"])
        self.assertIn(str(USER_ID), state["pending_member_ids"])
        self.assertFalse(state["approved_users_done"])
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.disconnected)

    def test_mismatched_missing_invitee_is_not_accepted(self):
        state, fake, _, exc = asyncio.run(self.attempt(
            SimpleNamespace(missing_invitees=[
                SimpleNamespace(user_id=USER_ID + 99)
            ])
        ))
        self.assertIsInstance(exc, policy.PolicyBlocked)
        self.assertIn("identity_mismatch", str(exc))
        self.assertEqual(state["accounts"]["1"]["member_adds"], 0)
        self.assertTrue(state["pending_member_actions"])
        self.assertTrue(fake.disconnected)

    def test_non_mutual_contact_is_terminal_denial_not_an_unknown_outcome(self):
        failure = safe_runtime.errors.UserNotMutualContactError(None)
        state, fake, result, exc = asyncio.run(self.attempt(failure))
        self.assertIsNone(exc)
        self.assertEqual(result, "not_addable")
        self.assertEqual(state["approved_users_done"]["@consentuser"]["reason"],
                         "UserNotMutualContactError")
        self.assertEqual(state["accounts"]["1"]["member_adds"], 0)
        self.assertFalse(state["pending_member_actions"])
        self.assertFalse(state["pending_member_ids"])
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.disconnected)


if __name__ == "__main__":
    unittest.main()
