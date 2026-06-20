from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    BackupItem,
    BackupManifest,
    DeploymentAudit,
    FeatureUsage,
    HostArtifact,
    MigrationPlan,
    ResourceUsage,
    ServiceTopology,
    SmokeCheck,
    SmokePlan,
)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def dump_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def load_audit(path: str | Path) -> DeploymentAudit:
    raw = load_json(path)
    return DeploymentAudit(
        name=raw["name"],
        host=raw["host"],
        gitea_version=raw["gitea_version"],
        postgres_version=raw["postgres_version"],
        app_ini_path=raw["app_ini_path"],
        data_root=raw["data_root"],
        service=ServiceTopology(**raw["service"]),
        resources=ResourceUsage(**raw["resources"]),
        features=FeatureUsage(**raw["features"]),
        notes=raw.get("notes", []),
        host_artifacts=[HostArtifact(**item) for item in raw.get("host_artifacts", [])],
    )


def dump_backup_manifest(path: str | Path, manifest: BackupManifest) -> None:
    dump_json(path, manifest.to_dict())


def dump_migration_plan(path: str | Path, plan: MigrationPlan) -> None:
    dump_json(path, plan.to_dict())


def dump_smoke_script(path: str | Path, smoke_plan: SmokePlan) -> None:
    Path(path).write_text(smoke_plan.to_script())


def load_backup_manifest(path: str | Path) -> BackupManifest:
    raw = load_json(path)
    return BackupManifest(
        deployment_name=raw["deployment_name"],
        backup_root_hint=raw["backup_root_hint"],
        vm_snapshot_required=raw["vm_snapshot_required"],
        items=[BackupItem(**item) for item in raw["items"]],
    )


def load_smoke_plan(path: str | Path) -> SmokePlan:
    raw = load_json(path)
    return SmokePlan(
        deployment_name=raw["deployment_name"],
        checks=[SmokeCheck(**item) for item in raw["checks"]],
    )
