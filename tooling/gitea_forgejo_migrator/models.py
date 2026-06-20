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
class HostArtifact:
    artifact_id: str
    category: str
    kind: str
    decision: str
    source: str
    reason: str
    path: str | None = None
    details: dict[str, str] = field(default_factory=dict)
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    host_artifacts: list[HostArtifact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AuditFinding:
    code: str
    severity: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DeploymentAuditOutcome:
    ready: bool
    risk_level: str
    findings: list[AuditFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "risk_level": self.risk_level,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(slots=True)
class DeploymentAuditReport:
    host_label: str
    service_model: str
    gitea_version: str
    database_backend: str
    database_version: str
    config_path: str
    data_root: str
    reverse_proxy: str
    reverse_proxy_port: int
    app_port: int
    repositories: int
    users: int
    org_memberships: int
    repository_storage_mb: float
    attachments_storage_mb: float
    lfs_objects: int
    actions_runs: int
    action_runners: int
    packages: int
    root_free_gb: float
    internal_ssh_server: bool
    lfs_enabled: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeploymentAuditReport":
        return cls(**payload)

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
