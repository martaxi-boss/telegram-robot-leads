"""Safe group review tests: only explicit, verified group selections modify vault."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import public_group_review as review
from public_group_discovery import write_catalog


class GroupReviewTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.catalog = self.state / "public-groups.json"
        write_catalog(self.catalog, {
            "schema": 1, "last_scan_at": "2026-10-19",
            "groups": {
                "@publiciptv": {
                    "username": "@PublicIPTV", "title": "Portuguese IPTV",
                    "matched_keywords": ["iptv portugal"],
                },
                "@othergroup": {
                    "username": "@OtherGroup", "title": "Another public group",
                    "matched_keywords": ["iptv"],
                },
            },
        })
        self.allowlist = self.vault / "group_allowlist.txt"

    def test_list_only_public_group_metadata(self):
        result = review.public_groups(self.catalog)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["username"], "@OtherGroup")
        self.assertEqual(result[1]["public_url"], "https://t.me/PublicIPTV")
        self.assertTrue(all("users" not in x for x in result))

    def test_unconfirmed_approval_is_not_written(self):
        with self.assertRaisesRegex(review.ReviewBlocked, "confirmation"):
            review.approve_group("@PublicIPTV", vault=self.vault,
                                 catalog_path=self.catalog)
        self.assertFalse(self.allowlist.exists())

    def test_selected_group_only_is_written_private_and_deduplicated(self):
        result = review.approve_group("@PublicIPTV", vault=self.vault,
                                       catalog_path=self.catalog, confirm=True)
        self.assertEqual(result["status"], "OPERATOR_GROUP_APPROVED")
        self.assertEqual(result["telegram_requests"], 0)
        self.assertEqual(result["group_joins"], 0)
        self.assertEqual(self.allowlist.read_text(), "@PublicIPTV\n")
        self.assertEqual(self.allowlist.stat().st_mode & 0o777, 0o600)
        same = review.approve_group("publiciptv", vault=self.vault,
                                    catalog_path=self.catalog, confirm=True)
        self.assertEqual(same["status"], "ALREADY_APPROVED")
        self.assertEqual(self.allowlist.read_text(), "@PublicIPTV\n")

    def test_preserve_existing_comments_and_approvals(self):
        self.allowlist.write_text("# approved earlier\n@OldGroup")
        self.allowlist.chmod(0o600)
        result = review.approve_group("@OtherGroup", vault=self.vault,
                                       catalog_path=self.catalog, confirm=True)
        self.assertEqual(result["approved_groups"], 2)
        self.assertEqual(self.allowlist.read_text(),
                         "# approved earlier\n@OldGroup\n@OtherGroup\n")

    def test_unknown_group_cannot_enter_auto_join_queue(self):
        with self.assertRaisesRegex(review.ReviewBlocked, "not_in_verified"):
            review.approve_group("@NotDiscovered", vault=self.vault,
                                 catalog_path=self.catalog, confirm=True)
        self.assertFalse(self.allowlist.exists())

    def test_symlink_and_insecure_allowlist_are_rejected(self):
        secret = self.root / "sensitive"
        secret.write_text("PRIVATE\n")
        self.allowlist.symlink_to(secret)
        with self.assertRaisesRegex(review.ReviewBlocked, "symlink"):
            review.approve_group("@PublicIPTV", vault=self.vault,
                                 catalog_path=self.catalog, confirm=True)
        self.assertEqual(secret.read_text(), "PRIVATE\n")
        self.allowlist.unlink()
        self.allowlist.write_text("@OldGroup\n")
        self.allowlist.chmod(0o644)
        with self.assertRaises(Exception):
            review.approve_group("@PublicIPTV", vault=self.vault,
                                 catalog_path=self.catalog, confirm=True)
        self.assertEqual(self.allowlist.read_text(), "@OldGroup\n")

    def test_insecure_vault_is_rejected(self):
        self.vault.chmod(0o755)
        with self.assertRaisesRegex(review.ReviewBlocked, "permissions"):
            review.approve_group("@PublicIPTV", vault=self.vault,
                                 catalog_path=self.catalog, confirm=True)
        self.assertFalse(self.allowlist.exists())

    def test_malformed_catalog_never_creates_allowlist(self):
        self.catalog.write_text("invalid")
        self.catalog.chmod(0o600)
        with self.assertRaises(Exception):
            review.approve_group("@PublicIPTV", vault=self.vault,
                                 catalog_path=self.catalog, confirm=True)
        self.assertFalse(self.allowlist.exists())

    def test_existing_operator_file_with_invalid_entries_is_untouched(self):
        self.allowlist.write_text("garbage handle with spaces")
        self.allowlist.chmod(0o600)
        with self.assertRaises(Exception):
            review.approve_group("@PublicIPTV", vault=self.vault,
                                 catalog_path=self.catalog, confirm=True)
        self.assertEqual(self.allowlist.read_text(), "garbage handle with spaces")

    def test_cannot_override_allowlist_outside_vault(self):
        with patch.dict(os.environ, {"TELEGRAM_GROUP_ALLOWLIST": "../other"}):
            with self.assertRaisesRegex(review.ReviewBlocked, "name_invalid"):
                review.approve_group("@PublicIPTV", vault=self.vault,
                                     catalog_path=self.catalog, confirm=True)
        self.assertFalse(self.allowlist.exists())


if __name__ == "__main__":
    unittest.main()
