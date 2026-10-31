"""Telegram official request-needed invite link: local offline no network tests."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import organic_growth as growth

LINK = "https://t.me/+ABCDEFGHIJKLMNO"
TARGET = "@iptvpncode"
TITLE = growth.VOLUNTARY_LINK_TITLE


def invite(*, link=LINK, title=TITLE, request_needed=True, revoked=False, expire_date=None):
    return SimpleNamespace(link=link, title=title, request_needed=request_needed,
                           revoked=revoked, expire_date=expire_date)


class FakeClient:
    def __init__(self, existing=None, owner=True, target_ok=True):
        self.existing = list(existing or [])
        self.owner = owner
        self.target_ok = target_ok
        self.connected = True
        self.disconnected = False
        self.requests = []

    async def get_entity(self, group):
        assert group == TARGET
        return SimpleNamespace(megagroup=self.target_ok, broadcast=False)

    async def get_permissions(self, group, person):
        assert person == "me"
        return SimpleNamespace(is_creator=self.owner, is_admin=self.owner,
                               invite_users=self.owner)

    async def __call__(self, request):
        self.requests.append(type(request).__name__)
        if isinstance(request, growth.GetExportedChatInvitesRequest):
            return SimpleNamespace(invites=self.existing)
        if isinstance(request, growth.GetExportedChatInviteRequest):
            return SimpleNamespace(invite=invite())
        if isinstance(request, growth.ExportChatInviteRequest):
            assert request.request_needed is True
            assert request.title == TITLE
            assert request.legacy_revoke_permanent is None
            return invite()
        raise AssertionError("Unexpected Telegram operation")

    def is_connected(self):
        return self.connected

    async def disconnect(self):
        self.disconnected = True
        self.connected = False


class OfficialVoluntaryLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        self.vault.chmod(0o700)
        self.config = {"group": TARGET}
        self.model = {"target_group": TARGET, "approve_join_requests": True}
        self.path = self.vault / growth.VOLUNTARY_LINK_FILE

    def execute(self, client, *, model=None):
        connector = AsyncMock(return_value=client)
        result = asyncio.run(growth.ensure_voluntary_request_link(
            self.config, self.model if model is None else model,
            self.vault, connector,
        ))
        connector.assert_awaited_once_with(self.config, 1)
        self.assertTrue(client.disconnected)
        return result

    def test_only_first_party_request_link_is_created_once(self):
        c = FakeClient()
        result = self.execute(c)
        self.assertEqual(result["status"], "CREATED")
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["members_added"], 0)
        self.assertEqual(c.requests, ["GetExportedChatInvitesRequest",
                                      "ExportChatInviteRequest"])
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["link"], LINK)
        self.assertEqual(saved["target_group"], TARGET)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_existing_link_verified_without_creating_another(self):
        self.execute(FakeClient())
        c = FakeClient()
        result = self.execute(c)
        self.assertEqual(result["status"], "EXISTING_VERIFIED")
        self.assertEqual(result["created"], 0)
        self.assertEqual(c.requests, ["GetExportedChatInviteRequest"])

    def test_reuse_named_link_if_previous_local_save_was_missing(self):
        c = FakeClient(existing=[invite()])
        result = self.execute(c)
        self.assertEqual(result["status"], "REUSED")
        self.assertEqual(c.requests, ["GetExportedChatInvitesRequest"])
        self.assertEqual(growth._read_voluntary_link(self.vault, TARGET), LINK)

    def test_refuse_wrong_link_type_instead_of_reusing(self):
        c = FakeClient(existing=[invite(request_needed=False)])
        with self.assertRaisesRegex(growth.ProbeBlocked, "not_an_active"):
            self.execute(c)
        self.assertEqual(c.requests, ["GetExportedChatInvitesRequest"])
        self.assertFalse(self.path.exists())

    def test_invalid_target_or_disabled_model_stops_before_connecting(self):
        for model in (
            {"target_group": TARGET, "approve_join_requests": False},
            {"target_group": "@othergroup", "approve_join_requests": True},
        ):
            connector = AsyncMock(side_effect=AssertionError("must not connect"))
            with self.assertRaisesRegex(growth.ProbeBlocked, "not_enabled"):
                asyncio.run(growth.ensure_voluntary_request_link(
                    self.config, model, self.vault, connector,
                ))
            connector.assert_not_awaited()

    def test_non_admin_does_not_create_a_link(self):
        c = FakeClient(owner=False)
        with self.assertRaisesRegex(growth.ProbeBlocked, "permission"):
            self.execute(c)
        self.assertFalse(self.path.exists())
        self.assertEqual(c.requests, [])

    def test_not_supergroup_cannot_create_link(self):
        c = FakeClient(target_ok=False)
        with self.assertRaisesRegex(growth.ProbeBlocked, "supergroup"):
            self.execute(c)
        self.assertEqual(c.requests, [])

    def test_duplicate_named_links_require_review(self):
        c = FakeClient(existing=[invite(), invite(link="https://t.me/+PQRSTUVWXYZabc")])
        with self.assertRaisesRegex(growth.ProbeBlocked, "duplicate"):
            self.execute(c)
        self.assertNotIn("ExportChatInviteRequest", c.requests)
        self.assertFalse(self.path.exists())

    def test_no_duplicate_creation_with_incomplete_inventory(self):
        c = FakeClient(existing=[invite(title="other") for _ in range(growth.MAX_EXISTING_INVITES)])
        with self.assertRaisesRegex(growth.ProbeBlocked, "incomplete"):
            self.execute(c)
        self.assertNotIn("ExportChatInviteRequest", c.requests)

    def test_saved_link_must_not_be_publicly_readable_or_symlinked(self):
        self.path.write_text(json.dumps({"schema": 1, "target_group": TARGET,
                                         "account": 1, "link": LINK}))
        self.path.chmod(0o644)
        connector = AsyncMock(side_effect=AssertionError("no request"))
        with self.assertRaisesRegex(growth.ProbeBlocked, "permissions"):
            asyncio.run(growth.ensure_voluntary_request_link(
                self.config, self.model, self.vault, connector))
        connector.assert_not_awaited()
        self.path.unlink()
        other = self.vault / "other"
        other.write_text("private")
        self.path.symlink_to(other)
        with self.assertRaisesRegex(growth.ProbeBlocked, "symlink"):
            asyncio.run(growth.ensure_voluntary_request_link(
                self.config, self.model, self.vault, connector))
        connector.assert_not_awaited()

    def test_invalid_link_type_and_expiry_are_rejected(self):
        for kwargs in (
            {"link": "https://t.me/iptvpncode"},
            {"request_needed": False},
            {"revoked": True},
            {"expire_date": 1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(growth.ProbeBlocked):
                growth._request_required_invite(invite(**kwargs))


if __name__ == "__main__":
    unittest.main()
