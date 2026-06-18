"""Structured models for backup planning and rollback manifests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any


def _require_absolute_path(value: str, field_name: str) -> str:
    path = PurePosixPath(value)
    if not path.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path: {value!r}")
    return str(path)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DeploymentInventory:
    """Deployment facts required to plan a backup and rollback."""

    instance_name: str
    hostname: str
    service_name: str
    gitea_version: str
    database_engine: str
    database_name: str
    config_path: str
    work_path: str
    data_path: str
    custom_path: str
    lfs_path: str
    log_path: str
    repo_storage_path: str
    attachments_path: str
    root_free_bytes: int
    work_dir_bytes: int
    repo_storage_bytes: int
    attachments_bytes: int
    lfs_bytes: int = 0
    actions_bytes: int = 0
    packages_bytes: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "config_path",
            "work_path",
            "data_path",
            "custom_path",
            "lfs_path",
            "log_path",
            "repo_storage_path",
            "attachments_path",
        ):
            value = getattr(self, field_name)
            object.__setattr__(self, field_name, _require_absolute_path(value, field_name))
        for field_name in (
            "root_free_bytes",
            "work_dir_bytes",
            "repo_storage_bytes",
            "attachments_bytes",
            "lfs_bytes",
            "actions_bytes",
            "packages_bytes",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")


@dataclass(frozen=True)
class IntegrityCheck:
    """A validation task that should be performed after an artifact is captured."""

    name: str
    command: str
    expectation: str


@dataclass(frozen=True)
class BackupArtifact:
    """A single required artifact in the migration backup set."""

    artifact_id: str
    kind: str
    source_path: str
    capture_method: str
    estimated_bytes: int
    required_for_rollback: bool
    mutates_during_runtime: bool
    integrity_checks: tuple[IntegrityCheck, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_path",
            _require_absolute_path(self.source_path, "source_path"),
        )
        if self.estimated_bytes < 0:
            raise ValueError("estimated_bytes must be non-negative")


@dataclass(frozen=True)
class RollbackStep:
    """An operator-visible rollback action."""

    order: int
    summary: str
    command_hint: str
    requires_full_restore: bool = False


@dataclass(frozen=True)
class RollbackPlan:
    """Rollback steps for a particular migration stage."""

    stage: str
    rationale: str
    steps: tuple[RollbackStep, ...]
    validated_with_manifest: str


@dataclass(frozen=True)
class BackupManifest:
    """Complete backup planning manifest."""

    manifest_version: str
    generated_at: datetime
    instance_name: str
    source_version: str
    database_engine: str
    maintenance_window: str
    artifacts: tuple[BackupArtifact, ...]
    estimated_backup_bytes: int
    minimum_recommended_free_bytes: int
    rollback_checkpoint: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.astimezone(timezone.utc).isoformat()
        return payload

    def artifact_ids(self) -> tuple[str, ...]:
        return tuple(artifact.artifact_id for artifact in self.artifacts)

