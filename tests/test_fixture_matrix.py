from __future__ import annotations

import unittest
from pathlib import Path

from gitea_forgejo_migrator.audit import evaluate_deployment
from gitea_forgejo_migrator.cli import _load_report, main
from gitea_forgejo_migrator.compatibility import assess_gitea_to_forgejo
from gitea_forgejo_migrator.io import load_audit


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FixtureMatrixTests(unittest.TestCase):
    def test_docker_fixture_is_medium_risk(self) -> None:
        report = _load_report(str(FIXTURES / "docker-audit.json"))
        outcome = evaluate_deployment(report)
        self.assertTrue(outcome.ready)
        self.assertEqual(outcome.risk_level, "medium")
        self.assertIn("service-model", {finding.code for finding in outcome.findings})
        self.assertIn("packages-usage", {finding.code for finding in outcome.findings})

    def test_sqlite_fixture_warns_on_backend(self) -> None:
        report = _load_report(str(FIXTURES / "sqlite-audit.json"))
        outcome = evaluate_deployment(report)
        self.assertTrue(outcome.ready)
        self.assertIn("database-backend", {finding.code for finding in outcome.findings})

    def test_actions_fixture_warns_on_actions(self) -> None:
        report = _load_report(str(FIXTURES / "actions-audit.json"))
        outcome = evaluate_deployment(report)
        self.assertIn("actions-usage", {finding.code for finding in outcome.findings})

    def test_lfs_heavy_fixture_warns_on_lfs(self) -> None:
        report = _load_report(str(FIXTURES / "lfs-heavy-audit.json"))
        outcome = evaluate_deployment(report)
        self.assertIn("lfs-usage", {finding.code for finding in outcome.findings})

    def test_gitea_123_fixture_is_blocked(self) -> None:
        path = FIXTURES / "gitea-123-blocked-audit.json"
        exit_code = main(["gate", str(path), "--target", "forgejo-current"])
        self.assertEqual(exit_code, 1)

    def test_gitea_123_fixture_has_no_supported_stages(self) -> None:
        audit = load_audit(FIXTURES / "gitea-123-blocked-audit.json")
        assessment = assess_gitea_to_forgejo(audit.gitea_version)
        self.assertFalse(assessment.supported)
        self.assertEqual(assessment.recommended_stages, [])


class FixtureCompatibilityTests(unittest.TestCase):
    def test_legacy_fixture_loader_still_works_for_matrix(self) -> None:
        audit = load_audit(FIXTURES / "docker-audit.json")
        self.assertEqual(audit.name, "docker-gitea")


if __name__ == "__main__":
    unittest.main()
