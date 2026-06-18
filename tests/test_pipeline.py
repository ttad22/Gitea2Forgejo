from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gitea_forgejo_migrator.backup import build_backup_manifest
from gitea_forgejo_migrator.io import load_audit
from gitea_forgejo_migrator.planning import build_migration_plan
from gitea_forgejo_migrator.simulate import build_simulation_report
from gitea_forgejo_migrator.smoke import build_smoke_plan


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vm100-audit.json"


class PipelineTests(unittest.TestCase):
    def test_fixture_loads(self) -> None:
        audit = load_audit(FIXTURE)
        self.assertEqual(audit.name, "git-ops")
        self.assertEqual(audit.features.repositories, 36)

    def test_backup_manifest_contains_db_dump(self) -> None:
        audit = load_audit(FIXTURE)
        manifest = build_backup_manifest(audit)
        labels = {item.label for item in manifest.items}
        self.assertIn("postgres_dump", labels)
        self.assertIn("app_ini", labels)

    def test_smoke_plan_targets_expected_services(self) -> None:
        audit = load_audit(FIXTURE)
        smoke = build_smoke_plan(audit)
        script = smoke.to_script()
        self.assertIn("systemctl is-active gitea", script)
        self.assertIn("curl -fsS http://127.0.0.1:3000/api/health", script)

    def test_migration_plan_has_expected_stages(self) -> None:
        audit = load_audit(FIXTURE)
        plan = build_migration_plan(audit)
        self.assertEqual(plan.stages, ["gitea-1.22.x", "forgejo-10.x", "forgejo-current"])

    def test_simulation_report_is_serializable(self) -> None:
        audit = load_audit(FIXTURE)
        report = build_simulation_report(audit)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text(json.dumps(report))
            self.assertTrue(path.read_text())


if __name__ == "__main__":
    unittest.main()
