"""Prevent regression to a second, nonfunctional SSH deployment route.

Deployment and the existing SSH password belong to martaxi-boss/VPS;
this repository only tests application code. These checks are offline.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CANONICAL_WORKFLOW = "safe-growth-checks.yml"


class DeploymentRouteTests(unittest.TestCase):
    def test_telegram_repo_has_one_ci_workflow_and_no_deploy_workflow(self):
        found = sorted(
            path.name for path in WORKFLOWS.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )
        self.assertEqual(found, [CANONICAL_WORKFLOW])

    def test_local_ci_does_not_use_ssh_or_github_secrets(self):
        source = (WORKFLOWS / CANONICAL_WORKFLOW).read_text(encoding="utf-8")
        for forbidden in (
            "secrets.", "sshpass", "ssh-keyscan", "scp ", "ssh -T",
            "TELEGRAM_LEADS_SSH_", "VPS_SSH_PASSWORD", "workflow_dispatch:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_single_existing_central_route_is_documented(self):
        source = (ROOT / "docs" / "TELEGRAM_ONLY_INSTALLATION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("martaxi-boss/VPS", source)
        self.assertIn("telegram-leads-vps-stage-20261019.yml", source)
        self.assertIn("VPS_SSH_PASSWORD", source)
        self.assertIn("7c0ef8a1d9be5d18568a133bcfdb79e4e0bcd9aa", source)
        self.assertIn("5ade747d82066515bc0032ca53639b13670ccc36", source)


if __name__ == "__main__":
    unittest.main()
