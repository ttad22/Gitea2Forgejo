from __future__ import annotations

from .compatibility import assess_gitea_to_forgejo
from .models import DeploymentAudit, MigrationPlan


def build_migration_plan(audit: DeploymentAudit) -> MigrationPlan:
    assessment = assess_gitea_to_forgejo(audit.gitea_version)
    if not assessment.supported:
        return MigrationPlan(
            deployment_name=audit.name,
            maintenance_window_minutes=0,
            stages=[],
            prerequisites=[
                "Stop: the source version is outside the supported direct staged path.",
                *assessment.warnings,
            ],
            rollback_summary=["No execution plan generated for unsupported source cohort."],
        )

    prerequisites = [
        "Confirm current backups are green.",
        "Take a VM snapshot.",
        "Generate a PostgreSQL dump.",
        "Archive /etc/gitea and /var/lib/gitea.",
        "Freeze writes during the cutover window.",
    ]
    rollback = [
        "Stop Forgejo.",
        "Restore the previous Gitea binary or package.",
        "Restore PostgreSQL dump if schema rollback is required.",
        "Restore /etc/gitea and /var/lib/gitea archives.",
        "Start Gitea and validate login, clone, and push.",
    ]
    return MigrationPlan(
        deployment_name=audit.name,
        maintenance_window_minutes=90,
        stages=["gitea-1.22.x", *assessment.recommended_stages],
        prerequisites=prerequisites,
        rollback_summary=rollback,
    )
