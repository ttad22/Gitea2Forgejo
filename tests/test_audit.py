from __future__ import annotations

import json
from pathlib import Path

from gitea_forgejo_migrator.audit import evaluate_deployment
from gitea_forgejo_migrator.models import DeploymentAuditReport


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def build_report(**overrides: object) -> DeploymentAuditReport:
    payload = {
        "host_label": "vm100",
        "service_model": "systemd",
        "gitea_version": "1.22.0",
        "database_backend": "postgresql",
        "database_version": "14.23",
        "config_path": "/etc/gitea/app.ini",
        "data_root": "/var/lib/gitea",
        "reverse_proxy": "nginx",
        "reverse_proxy_port": 80,
        "app_port": 3000,
        "repositories": 36,
        "users": 5,
        "org_memberships": 2,
        "repository_storage_mb": 795.0,
        "attachments_storage_mb": 80.0,
        "lfs_objects": 0,
        "actions_runs": 0,
        "action_runners": 0,
        "packages": 0,
        "root_free_gb": 188.0,
        "internal_ssh_server": False,
        "lfs_enabled": True,
    }
    payload.update(overrides)
    return DeploymentAuditReport.from_dict(payload)


def test_reference_report_is_ready() -> None:
    outcome = evaluate_deployment(build_report())
    assert outcome.ready is True
    assert outcome.risk_level == "low"
    assert [finding.code for finding in outcome.findings] == ["ssh-mode"]


def test_detects_feature_usage_and_model_drift() -> None:
    outcome = evaluate_deployment(
        build_report(
            service_model="docker",
            database_backend="sqlite",
            actions_runs=12,
            action_runners=1,
            packages=4,
            lfs_objects=9,
        )
    )
    assert outcome.ready is True
    assert outcome.risk_level == "medium"
    assert {finding.code for finding in outcome.findings} >= {
        "service-model",
        "database-backend",
        "actions-usage",
        "packages-usage",
        "lfs-usage",
    }


def test_detects_insufficient_disk_as_blocker() -> None:
    outcome = evaluate_deployment(build_report(root_free_gb=1.5))
    assert outcome.ready is False
    assert outcome.risk_level == "high"
    assert any(finding.code == "disk-headroom" and finding.severity == "blocker" for finding in outcome.findings)


def load_report_fixture(name: str) -> DeploymentAuditReport:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return DeploymentAuditReport.from_dict(
        {
            "host_label": payload["name"],
            "service_model": "docker" if "docker" in payload["service"]["install_mode"] else "systemd",
            "gitea_version": payload["gitea_version"],
            "database_backend": payload["service"]["database"],
            "database_version": payload["postgres_version"],
            "config_path": payload["app_ini_path"],
            "data_root": payload["data_root"],
            "reverse_proxy": payload["service"]["reverse_proxy"],
            "reverse_proxy_port": 80,
            "app_port": 3000,
            "repositories": payload["features"]["repositories"],
            "users": payload["features"]["users"],
            "org_memberships": payload["features"]["org_memberships"],
            "repository_storage_mb": payload["resources"]["repositories_mb"],
            "attachments_storage_mb": payload["resources"]["attachments_mb"],
            "lfs_objects": payload["features"]["lfs_objects"],
            "actions_runs": payload["features"]["action_runs"],
            "action_runners": payload["features"]["action_runners"],
            "packages": payload["features"]["packages"],
            "root_free_gb": payload["resources"]["root_free_gb"],
            "internal_ssh_server": payload["service"]["ssh_mode"] == "embedded-ssh",
            "lfs_enabled": payload["resources"]["lfs_mb"] > 0.0,
        }
    )


def test_docker_fixture_flags_service_model_and_usage_findings() -> None:
    outcome = evaluate_deployment(load_report_fixture("docker-audit.json"))
    assert outcome.ready is True
    assert outcome.risk_level == "medium"
    assert {finding.code for finding in outcome.findings} >= {
        "service-model",
        "lfs-usage",
        "packages-usage",
    }


def test_sqlite_fixture_flags_non_reference_database_only() -> None:
    outcome = evaluate_deployment(load_report_fixture("sqlite-audit.json"))
    assert outcome.ready is True
    assert outcome.risk_level == "medium"
    assert {finding.code for finding in outcome.findings} == {"database-backend"}


def test_actions_fixture_requires_explicit_actions_validation() -> None:
    outcome = evaluate_deployment(load_report_fixture("actions-audit.json"))
    assert outcome.ready is True
    assert outcome.risk_level == "medium"
    assert {finding.code for finding in outcome.findings} >= {"ssh-mode", "actions-usage"}


def test_lfs_heavy_fixture_keeps_readiness_but_marks_lfs_risk() -> None:
    outcome = evaluate_deployment(load_report_fixture("lfs-heavy-audit.json"))
    assert outcome.ready is True
    assert outcome.risk_level == "medium"
    assert {finding.code for finding in outcome.findings} == {"ssh-mode", "lfs-usage"}
