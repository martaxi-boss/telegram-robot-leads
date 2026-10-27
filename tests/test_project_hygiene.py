"""Verify Telegram Robot Leads hygiene cannot delete secrets or other projects."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_hygiene as hygiene


class HygieneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "scripts" / "__pycache__").mkdir()
        (self.root / "tests" / "__pycache__").mkdir()
        (self.root / "__pycache__").mkdir()
        for path in (
            self.root / "__pycache__" / "module.pyc",
            self.root / "scripts" / "__pycache__" / "helper.pyc",
            self.root / "tests" / "__pycache__" / "fixture.pyc",
        ):
            path.write_bytes(b"\0\0bytecode")
        for relative in (
            "main.py", "some.session", "accounts.json", "state.json",
            "project-backup.tar.gz", "operation-state.json",
            "supervisor-events.jsonl",
        ):
            (self.root / relative).write_text("must remain unchanged")
        self.outside = self.root.parent / (self.root.name + ".another-project")
        self.outside.write_text("other project must remain intact")
        self.addCleanup(lambda: self.outside.unlink(missing_ok=True))

    def test_dry_run_does_not_remove_anything(self):
        observed = hygiene.clean(self.root)
        self.assertEqual(observed["status"], "DRY_RUN")
        self.assertEqual(observed["eligible_python_cache_files"], 3)
        self.assertEqual(observed["removed_files"], 0)
        self.assertTrue((self.root / "__pycache__" / "module.pyc").exists())

    def test_apply_is_canonical_root_only_and_preserves_all_non_cache_files(self):
        with self.assertRaisesRegex(hygiene.HygieneBlocked, "canonical"):
            hygiene.clean(self.root, apply=True)
        with patch.object(hygiene, "CANONICAL_ROOT", self.root):
            result = hygiene.clean(self.root, apply=True)
        self.assertEqual(result["removed_files"], 3)
        self.assertTrue(result["status"] == "APPLIED")
        for relative in (
            "main.py", "some.session", "accounts.json", "state.json",
            "project-backup.tar.gz", "operation-state.json",
            "supervisor-events.jsonl",
        ):
            self.assertEqual((self.root / relative).read_text(), "must remain unchanged")
        self.assertEqual(self.outside.read_text(), "other project must remain intact")

    def test_refuses_unknown_files_in_python_cache(self):
        (self.root / "scripts" / "__pycache__" / "notes.txt").write_text("do not touch")
        with self.assertRaisesRegex(hygiene.HygieneBlocked, "unexpected_cache_content"):
            hygiene.plan(self.root)
        self.assertTrue((self.root / "__pycache__" / "module.pyc").exists())

    def test_refuses_symlink_inside_cache(self):
        cache = self.root / "scripts" / "__pycache__"
        (cache / "link.pyc").symlink_to(self.outside)
        with self.assertRaisesRegex(hygiene.HygieneBlocked, "unexpected_cache_content"):
            hygiene.plan(self.root)
        self.assertEqual(self.outside.read_text(), "other project must remain intact")

    def test_refuses_parent_alias_to_other_project(self):
        for file in (self.root / "scripts" / "__pycache__").iterdir():
            file.unlink()
        (self.root / "scripts" / "__pycache__").rmdir()
        (self.root / "scripts").rmdir()
        (self.root / "scripts").symlink_to(self.root / "tests", target_is_directory=True)
        with self.assertRaisesRegex(hygiene.HygieneBlocked, "directory_not_private_owned"):
            hygiene.plan(self.root)


if __name__ == "__main__":
    unittest.main()
