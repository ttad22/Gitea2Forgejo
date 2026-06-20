from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gitea_forgejo_migrator.backup import build_backup_manifest
from gitea_forgejo_migrator.io import load_audit
from gitea_forgejo_migrator.local import build_local_runner_script
from gitea_forgejo_migrator.models import HostArtifact
from gitea_forgejo_migrator.planning import build_migration_plan
from gitea_forgejo_migrator.simulate import build_simulation_report
from gitea_forgejo_migrator.smoke import build_smoke_plan


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "systemd-postgres-nginx-audit.json"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class PipelineTests(unittest.TestCase):
    def test_fixture_loads(self) -> None:
        audit = load_audit(FIXTURE)
        self.assertEqual(audit.name, "git-example")
        self.assertEqual(audit.features.repositories, 36)

    def test_backup_manifest_contains_db_dump(self) -> None:
        audit = load_audit(FIXTURE)
        manifest = build_backup_manifest(audit)
        labels = {item.label for item in manifest.items}
        self.assertIn("postgres_dump", labels)
        self.assertIn("app_ini", labels)
        dump = next(item for item in manifest.items if item.label == "postgres_dump")
        self.assertIn("pg_dump -Fc gitea", dump.command)

    def test_backup_manifest_uses_discovered_database_name(self) -> None:
        audit = load_audit(FIXTURE)
        audit.notes = [note for note in audit.notes if not note.startswith("database_name=")]
        audit.notes.append("database_name=codeforge")
        manifest = build_backup_manifest(audit)
        dump = next(item for item in manifest.items if item.label == "postgres_dump")
        self.assertIn("pg_dump -Fc codeforge", dump.command)

    def test_smoke_plan_targets_expected_services(self) -> None:
        audit = load_audit(FIXTURE)
        smoke = build_smoke_plan(audit)
        script = smoke.to_script()
        self.assertIn("systemctl is-active gitea", script)
        self.assertIn("curl -fsS http://127.0.0.1:3000/api/health", script)
        self.assertIn("https://git.example.org/", script)
        self.assertIn("ssh_authorized_keys", script)

    def test_backup_manifest_preserves_supported_cohort_paths(self) -> None:
        audit = load_audit(FIXTURE)
        manifest = build_backup_manifest(audit)
        labels = {item.label for item in manifest.items}
        assert "data" in labels
        assert "ssh_authorized_keys" in labels
        assert "repository_root" not in labels

    def test_backup_manifest_includes_discovered_config_paths(self) -> None:
        audit = load_audit(FIXTURE)
        audit.notes.append("preserve_path:file:server.cert_file=/etc/gitea/tls/server.crt")
        audit.notes.append("preserve_path:directory:mailer.template_dir=/opt/gitea-mail/templates")
        manifest = build_backup_manifest(audit)
        labels = {item.label for item in manifest.items}
        assert "config_server_cert_file" in labels
        assert "config_mailer_template_dir" in labels

    def test_backup_manifest_includes_host_artifact_paths(self) -> None:
        audit = load_audit(FIXTURE)
        audit.host_artifacts.extend(
            [
                HostArtifact(
                    artifact_id="systemd_dropin_override",
                    category="systemd",
                    kind="dropin",
                    decision="manual_review",
                    source="systemd_scan",
                    reason="Override file",
                    path="/etc/systemd/system/gitea.service.d/override.conf",
                ),
                HostArtifact(
                    artifact_id="nginx_site_git",
                    category="nginx",
                    kind="file",
                    decision="preserved_external",
                    source="nginx_scan",
                    reason="Nginx site",
                    path="/etc/nginx/sites-enabled/git.conf",
                ),
            ]
        )
        manifest = build_backup_manifest(audit)
        labels = {item.label for item in manifest.items}
        assert "artifact_systemd_dropin_override" in labels
        assert "artifact_nginx_site_git" in labels

    def test_backup_manifest_skips_artifacts_already_covered_by_data_archive(self) -> None:
        audit = load_audit(FIXTURE)
        audit.host_artifacts.append(
            HostArtifact(
                artifact_id="hook_under_repo_root",
                category="git_hook",
                kind="file",
                decision="manual_review",
                source="hook_scan",
                reason="Repo-local hook",
                path="/var/lib/gitea/data/gitea-repositories/org/repo.git/hooks/post-receive",
            )
        )
        manifest = build_backup_manifest(audit)
        labels = {item.label for item in manifest.items}
        assert "artifact_hook_under_repo_root" not in labels

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

    def test_local_runner_script_references_preflight_local(self) -> None:
        script = build_local_runner_script("./gfm-audit.json")
        self.assertIn("preflight-local", script)
        self.assertIn("gfm-audit.json", script)

    def test_docker_fixture_loads_with_container_service_name(self) -> None:
        audit = load_audit(FIXTURES / "docker-audit.json")
        self.assertEqual(audit.service.install_mode, "docker-compose")
        self.assertEqual(audit.service.app_service_name, "docker-gitea")

    def test_sqlite_fixture_preserves_non_postgres_backend(self) -> None:
        audit = load_audit(FIXTURES / "sqlite-audit.json")
        self.assertEqual(audit.service.database, "sqlite")
        self.assertEqual(audit.postgres_version, "n/a")

    def test_actions_fixture_smoke_plan_keeps_reference_http_healthcheck(self) -> None:
        audit = load_audit(FIXTURES / "actions-audit.json")
        smoke = build_smoke_plan(audit)
        script = smoke.to_script()
        self.assertIn("curl -fsS http://127.0.0.1:3000/api/health", script)
        self.assertIn("systemctl is-active gitea", script)
        self.assertIn("https://actions.example.internal/", script)

    def test_lfs_heavy_fixture_backup_manifest_includes_lfs_archive(self) -> None:
        audit = load_audit(FIXTURES / "lfs-heavy-audit.json")
        manifest = build_backup_manifest(audit)
        lfs_item = next(item for item in manifest.items if item.label == "lfs")
        self.assertEqual(lfs_item.path, "/var/lib/gitea/lfs")
        self.assertTrue(manifest.vm_snapshot_required)

    def test_gitea_123_fixture_generates_blocked_plan(self) -> None:
        audit = load_audit(FIXTURES / "gitea-123-blocked-audit.json")
        plan = build_migration_plan(audit)
        self.assertEqual(plan.stages, [])
        self.assertEqual(plan.maintenance_window_minutes, 0)
        self.assertIn("outside the supported direct staged path", plan.prerequisites[0])


if __name__ == "__main__":
    unittest.main()
