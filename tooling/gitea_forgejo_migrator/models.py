from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ServiceTopology:
    install_mode: str
    reverse_proxy: str
    database: str
    app_service_name: str
    ssh_mode: str


@dataclass(slots=True)
class ResourceUsage:
    root_free_gb: float
    gitea_total_mb: float
    repositories_mb: float
    attachments_mb: float
    lfs_mb: float
    packages_mb: float


@dataclass(slots=True)
class FeatureUsage:
    repositories: int
    users: int
    org_memberships: int
    lfs_objects: int
    action_runs: int
    action_runners: int
    packages: int


@dataclass(slots=True)
class DeploymentAudit:
    name: str
    host: str
    gitea_version: str
    postgres_version: str
    app_ini_path: str
    data_root: str
    service: ServiceTopology
    resources: ResourceUsage
    features: FeatureUsage
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CompatibilityAssessment:
    source_version: str
    supported: bool
    reason: str
    recommended_stages: list[str]
    risk_level: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BackupItem:
    label: str
    kind: str
    path: str | None = None
    command: str | None = None
    required: bool = True


@dataclass(slots=True)
class BackupManifest:
    deployment_name: str
    backup_root_hint: str
    vm_snapshot_required: bool
    items: list[BackupItem]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass(slots=True)
class SmokeCheck:
    name: str
    command: str
    critical: bool = True


@dataclass(slots=True)
class SmokePlan:
    deployment_name: str
    checks: list[SmokeCheck]

    def to_script(self) -> str:
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            f'echo "Smoke plan for {self.deployment_name}"',
        ]
        for check in self.checks:
            lines.append(f'echo "== {check.name} =="')
            lines.append(check.command)
        lines.append('echo "smoke-plan-complete"')
        return "\n".join(lines) + "\n"


@dataclass(slots=True)
class MigrationPlan:
    deployment_name: str
    maintenance_window_minutes: int
    stages: list[str]
    prerequisites: list[str]
    rollback_summary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
