from __future__ import annotations

import json

from gitea_forgejo_migrator.cli import main
from gitea_forgejo_migrator.local import build_local_runner_script
from gitea_forgejo_migrator.models import DeploymentAudit, FeatureUsage, ResourceUsage, ServiceTopology
from gitea_forgejo_migrator.preflight import run_local_preflight


def _build_live_audit() -> DeploymentAudit:
    return DeploymentAudit(
        name="vm100",
        host="localhost",
        gitea_version="1.22.0",
        postgres_version="PostgreSQL 14",
        app_ini_path="/etc/gitea/app.ini",
        data_root="/var/lib/gitea",
        service=ServiceTopology(
            install_mode="systemd-binary",
            reverse_proxy="nginx",
            database="postgresql",
            app_service_name="gitea",
            ssh_mode="host-sshd",
        ),
        resources=ResourceUsage(
            root_free_gb=188.0,
            gitea_total_mb=1024.0,
            repositories_mb=795.0,
            attachments_mb=80.0,
            lfs_mb=0.0,
            packages_mb=0.0,
        ),
        features=FeatureUsage(
            repositories=36,
            users=5,
            org_memberships=2,
            lfs_objects=0,
            action_runs=0,
            action_runners=0,
            packages=0,
        ),
        notes=[],
    )


def test_build_local_runner_script_targets_preflight_bundle() -> None:
    script = build_local_runner_script("./gfm-preflight")
    assert "preflight-local" in script
    assert "GFM_TOOLING_ROOT" in script
    assert "preflight-bundle=$OUTDIR" in script


def test_run_local_preflight_writes_bundle(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "gitea_forgejo_migrator.preflight.collect_live_audit",
        lambda runner, app_ini_path, data_root: _build_live_audit(),
    )

    exit_code, paths, bundle = run_local_preflight(tmp_path / "bundle")

    assert exit_code == 0
    assert paths["audit"].exists()
    assert paths["preflight"].exists()
    saved = json.loads(paths["preflight"].read_text(encoding="utf-8"))
    assert saved["audit"]["host"] == "localhost"
    assert bundle["readiness"]["ready"] is True
    assert saved["simulation"]["compatibility"]["supported"] is True


def test_cli_preflight_local_reports_bundle(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "gitea_forgejo_migrator.preflight.collect_live_audit",
        lambda runner, app_ini_path, data_root: _build_live_audit(),
    )

    exit_code = main(["preflight-local", "--output-dir", str(tmp_path / "bundle")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "preflight.json" in captured.out
    assert "ready: yes" in captured.out
