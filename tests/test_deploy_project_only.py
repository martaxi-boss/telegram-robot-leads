"""Offline, no-SSH tests for narrowly scoped Telegram Robot Leads installation."""
from pathlib import Path
from unittest.mock import patch
import io
import os
import stat
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deploy_project_only as deploy

OLD = "d8736bd359de795182ee717448c93df2977d0a44"
NEW = "f" * 40


class InstallerTests(unittest.TestCase):
    def test_release_manifest_includes_regional_discovery_module(self):
        # Without this entry, a validated regional discovery release may
        # crash against the previous module's function signature on the VPS.
        self.assertIn("scripts/public_group_discovery.py", deploy.RUNTIME_FILES)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "telegram-robot-leads"
        self.root.mkdir()
        (self.root / "scripts").mkdir()
        (self.root / ".venv" / "bin").mkdir(parents=True)
        (self.root / ".venv" / "bin" / "python").write_text("virtual environment intact")
        (self.root / "main.py").write_text("safe entrypoint intact")
        (self.root / ".verified-source-commit").write_text(OLD + "\n")
        (self.root / ".verified-source-commit").chmod(0o600)
        self.vault = self.home / "vault"
        self.vault.mkdir()
        for i in (1, 2):
            session = self.vault / ("existing_" + str(i) + ".session")
            session.write_bytes(b"session must remain untouched")
            session.chmod(0o600)
        self.other_project = self.home / "unrelated-project"
        self.other_project.mkdir()
        (self.other_project / "keep.txt").write_text("untouched")
        self.private_state = self.home / "operation-state.json"
        self.private_state.write_text("preserve all state")
        self.archive = self.root / ".telegram-leads-example.tgz"
        self.original = {name: (b"# old code\n" if name.endswith(".py")
                                else b"#!/bin/sh\n") for name in deploy.RUNTIME_FILES
                         if name != "scripts/organic_growth.py"}
        for name, data in self.original.items():
            (self.root / name).write_bytes(data)
        self.contents = {name: (b"# new verified code\n" if name.endswith(".py")
                                else b"#!/bin/sh\n") for name in deploy.RUNTIME_FILES}
        self.build_archive()
        self.patcher = patch.multiple(deploy, ROOT=self.root, VAULT=self.vault)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def build_archive(self, overrides=None):
        entries = dict(self.contents)
        if overrides is not None:
            entries = overrides
        with tarfile.open(self.archive, "w:gz") as tar:
            for name, payload in entries.items():
                item = tarfile.TarInfo(name)
                item.size = len(payload)
                item.mode = 0o644
                tar.addfile(item, io.BytesIO(payload))

    def test_dry_run_never_changes_project(self):
        outcome = deploy.install(self.archive, NEW, OLD)
        self.assertEqual(outcome["status"], "DRY_RUN")
        self.assertEqual(outcome["sessions_preserved"], 2)
        self.assertEqual((self.root / "scripts" / "lead_health.py").read_bytes(),
                         b"# old code\n")
        self.assertFalse((self.root / deploy.BACKUP_NAME).exists())

    def test_applied_install_updates_only_named_files_and_backs_up_old_code(self):
        outcome = deploy.install(self.archive, NEW, OLD, apply=True)
        self.assertEqual(outcome["status"], "STAGED_NOT_ACTIVATED")
        self.assertEqual(outcome["installed_sha"], NEW)
        self.assertEqual(outcome["runtime_files"], len(deploy.RUNTIME_FILES))
        for name, payload in self.contents.items():
            self.assertEqual((self.root / name).read_bytes(), payload)
        backup = self.root / outcome["backup_directory"]
        self.assertEqual((backup / "scripts" / "lead_health.py").read_bytes(),
                         b"# old code\n")
        self.assertEqual((self.vault / "existing_1.session").read_bytes(),
                         b"session must remain untouched")
        self.assertEqual((self.vault / "existing_2.session").read_bytes(),
                         b"session must remain untouched")
        self.assertEqual(self.private_state.read_text(), "preserve all state")
        self.assertEqual((self.other_project / "keep.txt").read_text(), "untouched")
        self.assertEqual((self.root / "main.py").read_text(), "safe entrypoint intact")
        self.assertEqual((self.root / ".venv" / "bin" / "python").read_text(),
                         "virtual environment intact")
        with self.assertRaisesRegex(deploy.InstallBlocked, "installed_sha_mismatch"):
            deploy.install(self.archive, OLD, OLD, apply=True)

    def test_installed_sha_mismatch_does_not_modify_anything(self):
        with self.assertRaisesRegex(deploy.InstallBlocked, "installed_sha_mismatch"):
            deploy.install(self.archive, NEW, "a" * 40, apply=True)
        self.assertEqual((self.root / ".verified-source-commit").read_text(),
                         OLD + "\n")
        self.assertFalse((self.root / deploy.BACKUP_NAME).exists())

    def test_malicious_paths_and_symlinks_are_never_extracted(self):
        entries = dict(self.contents)
        entries["../unrelated-project/keep.txt"] = b"attack"
        self.build_archive(entries)
        with self.assertRaisesRegex(deploy.InstallBlocked, "bundle_unexpected_entry"):
            deploy.install(self.archive, NEW, OLD, apply=True)
        self.assertEqual((self.other_project / "keep.txt").read_text(), "untouched")
        self.assertFalse((self.root / deploy.BACKUP_NAME).exists())

    def test_missing_project_sessions_stop_before_any_changes(self):
        (self.vault / "existing_2.session").unlink()
        with self.assertRaisesRegex(deploy.InstallBlocked, "two_existing_sessions"):
            deploy.install(self.archive, NEW, OLD, apply=True)
        self.assertEqual((self.root / ".verified-source-commit").read_text(),
                         OLD + "\n")

    def test_missing_bundle_file_stops_before_any_changes(self):
        incomplete = dict(self.contents)
        incomplete.pop("scripts/safe_runtime.py")
        self.build_archive(incomplete)
        with self.assertRaisesRegex(deploy.InstallBlocked, "bundle_incomplete"):
            deploy.install(self.archive, NEW, OLD, apply=True)
        self.assertEqual((self.root / ".verified-source-commit").read_text(),
                         OLD + "\n")

    def test_destination_symlink_to_other_project_is_refused(self):
        target = self.root / "scripts" / "safe_runtime.py"
        target.unlink()
        target.symlink_to(self.other_project / "keep.txt")
        with self.assertRaisesRegex(deploy.InstallBlocked, "symlink"):
            deploy.install(self.archive, NEW, OLD, apply=True)
        self.assertEqual((self.other_project / "keep.txt").read_text(), "untouched")

    def test_preflight_blocks_invalid_python_before_copy(self):
        entries = dict(self.contents)
        entries["scripts/safe_runtime.py"] = b"def nope(:\n"
        self.build_archive(entries)
        with self.assertRaisesRegex(deploy.InstallBlocked, "bundle_python_syntax"):
            deploy.install(self.archive, NEW, OLD, apply=True)
        self.assertFalse((self.root / deploy.BACKUP_NAME).exists())


if __name__ == "__main__":
    unittest.main()
