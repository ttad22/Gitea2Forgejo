from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import evaluate_deployment
from .discovery import collect_live_audit
from .io import dump_json
from .models import DeploymentAudit, DeploymentAuditReport
from .shell import ShellRunner
from .simulate import build_simulation_report


def build_preflight_bundle(
    runner: ShellRunner,
    *,
    app_ini_path: str = "/etc/gitea/app.ini",
    data_root: str = "/var/lib/gitea",
) -> dict[str, Any]:
    audit = collect_live_audit(runner, app_ini_path=app_ini_path, data_root=data_root)
    readiness = evaluate_deployment(_report_from_audit(audit))
    simulation = build_simulation_report(audit)
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "audit": audit.to_dict(),
        "readiness": readiness.to_dict(),
        "simulation": simulation,
    }


def write_preflight_bundle(output_dir: str | Path, bundle: dict[str, Any]) -> dict[str, Path]:
    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    audit_path = base_path / "audit.json"
    preflight_path = base_path / "preflight.json"
    dump_json(audit_path, bundle["audit"])
    dump_json(preflight_path, bundle)
    return {"output_dir": base_path, "audit": audit_path, "preflight": preflight_path}


def run_local_preflight(
    output_dir: str | Path,
    *,
    app_ini_path: str = "/etc/gitea/app.ini",
    data_root: str = "/var/lib/gitea",
) -> tuple[int, dict[str, Path], dict[str, Any]]:
    bundle = build_preflight_bundle(
        ShellRunner(),
        app_ini_path=app_ini_path,
        data_root=data_root,
    )
    paths = write_preflight_bundle(output_dir, bundle)
    readiness = bundle["readiness"]["ready"]
    compatibility = bundle["simulation"]["compatibility"]["supported"]
    return (0 if readiness and compatibility else 1), paths, bundle


def _report_from_audit(audit: DeploymentAudit) -> DeploymentAuditReport:
    return DeploymentAuditReport(
        host_label=audit.name,
        service_model="systemd" if audit.service.install_mode.startswith("systemd") else audit.service.install_mode,
        gitea_version=audit.gitea_version,
        database_backend=audit.service.database,
        database_version=audit.postgres_version,
        config_path=audit.app_ini_path,
        data_root=audit.data_root,
        reverse_proxy=audit.service.reverse_proxy,
        reverse_proxy_port=80,
        app_port=3000,
        repositories=audit.features.repositories,
        users=audit.features.users,
        org_memberships=audit.features.org_memberships,
        repository_storage_mb=audit.resources.repositories_mb,
        attachments_storage_mb=audit.resources.attachments_mb,
        lfs_objects=audit.features.lfs_objects,
        actions_runs=audit.features.action_runs,
        action_runners=audit.features.action_runners,
        packages=audit.features.packages,
        root_free_gb=audit.resources.root_free_gb,
        internal_ssh_server=audit.service.ssh_mode != "host-sshd",
        lfs_enabled=audit.resources.lfs_mb > 0.0 or audit.features.lfs_objects > 0,
    )
