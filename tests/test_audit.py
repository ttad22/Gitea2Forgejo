from __future__ import annotations

from gitea_forgejo_migrator.audit import evaluate_deployment
from gitea_forgejo_migrator.models import DeploymentAuditReport


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
