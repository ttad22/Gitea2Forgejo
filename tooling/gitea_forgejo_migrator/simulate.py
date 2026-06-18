from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .backup import build_backup_manifest
from .compatibility import assess_gitea_to_forgejo
from .models import DeploymentAudit
from .planning import build_migration_plan
from .smoke import build_smoke_plan


def build_simulation_report(audit: DeploymentAudit) -> dict[str, Any]:
    compatibility = assess_gitea_to_forgejo(audit.gitea_version)
    manifest = build_backup_manifest(audit)
    smoke_plan = build_smoke_plan(audit)
    migration = build_migration_plan(audit)
    return {
        "audit": audit.to_dict(),
        "compatibility": compatibility.to_dict(),
        "backup_manifest": manifest.to_dict(),
        "migration_plan": migration.to_dict(),
        "smoke_plan": {
            "deployment_name": smoke_plan.deployment_name,
            "checks": [asdict(check) for check in smoke_plan.checks],
        },
    }
