"""Offline verification that targeted activation cannot touch another PM2 app."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, call
import tempfile
import os
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import activate_project_only as activation

SHA = "a" * 40
PM2HOME = Path("/root/.pm2")


class ProjectActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".verified-source-commit").write_text(SHA + "\n")
        self.active = patch.object(activation, "ROOT", self.root)
        self.active.start()
        self.addCleanup(self.active.stop)
        self.worker = {
            "name": "telegram-robot-leads",
            "pm2_env": {
                "pm_cwd": str(self.root),
                "pm_exec_path": str(self.root / "main.py"),
                "status": "online",
            },
        }

    def test_no_pm2_query_when_commit_is_wrong(self):
        with patch.object(activation, "_check_daemon_home",
                          side_effect=AssertionError("Should not touch PM2")):
            with self.assertRaisesRegex(
                activation.ActivationBlocked, "installed_commit_mismatch"
            ):
                activation.activate(PM2HOME, "b" * 40, apply=True)

    def test_no_pm2_query_when_daemon_is_unverified(self):
        with patch.object(activation, "_check_daemon_home",
                          side_effect=activation.ActivationBlocked("not_verified")):
            with patch.object(
                activation.subprocess, "run",
                side_effect=AssertionError("Never call PM2"),
            ):
                with self.assertRaisesRegex(
                    activation.ActivationBlocked, "not_verified"
                ):
                    activation.activate(PM2HOME, SHA, apply=True)

    def test_dry_run_never_restarts_a_worker(self):
        with patch.object(activation, "_check_daemon_home", return_value=500), \
             patch.object(activation, "_read_worker", return_value=self.worker), \
             patch.object(activation.subprocess, "run",
                          side_effect=AssertionError("No restart during dry run")):
            outcome = activation.activate(PM2HOME, SHA)
        self.assertEqual(outcome["status"], "READY_FOR_TARGETED_RESTART")

    def test_activation_only_restarts_exact_telegram_leads_name(self):
        with patch.object(activation, "_check_daemon_home", return_value=500), \
             patch.object(activation, "_read_worker", return_value=self.worker), \
             patch.object(activation.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0)) as process:
            outcome = activation.activate(PM2HOME, SHA, apply=True)
        process.assert_called_once()
        args = process.call_args.args[0]
        self.assertEqual(args, ["pm2", "restart", "telegram-robot-leads"])
        self.assertNotIn("--update-env", args)
        self.assertEqual(outcome["status"], "PROJECT_WORKER_RESTARTED")

    def test_pm2_listing_refuses_worker_with_another_project_path(self):
        other = {
            "name": "telegram-robot-leads",
            "pm2_env": {
                "pm_cwd": "/opt/unrelated-project",
                "pm_exec_path": "/opt/unrelated-project/main.py",
                "status": "online",
            },
        }
        with patch.object(activation, "_check_daemon_home", return_value=500), \
             patch.object(activation.subprocess, "run", return_value=SimpleNamespace(
                 returncode=0, stdout=json.dumps([other]), stderr=""
             )) as process:
            with self.assertRaisesRegex(
                activation.ActivationBlocked, "path_mismatch"
            ):
                activation.activate(PM2HOME, SHA, apply=True)
        self.assertEqual(process.call_count, 1)
        self.assertEqual(process.call_args.args[0], ["pm2", "jlist"])

    def test_pm2_listing_refuses_duplicate_worker_names(self):
        with patch.object(activation, "_check_daemon_home", return_value=500), \
             patch.object(activation.subprocess, "run", return_value=SimpleNamespace(
                 returncode=0, stdout=json.dumps([self.worker, self.worker]), stderr=""
             )) as process:
            with self.assertRaisesRegex(
                activation.ActivationBlocked, "missing_or_duplicate"
            ):
                activation.activate(PM2HOME, SHA, apply=True)
        self.assertEqual(process.call_count, 1)


if __name__ == "__main__":
    unittest.main()
