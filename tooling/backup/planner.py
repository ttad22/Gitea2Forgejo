"""Planning helpers for migration backup manifests and rollback instructions."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    BackupArtifact,
    BackupManifest,
    DeploymentInventory,
    IntegrityCheck,
    RollbackPlan,
    RollbackStep,
)

MANIFEST_VERSION = "2026-06-18"
_DEFAULT_MAINTENANCE_WINDOW = "60-90 minutes"
_DB_DUMP_OVERHEAD_RATIO = 0.20
_RECOMMENDED_FREE_SPACE_MULTIPLIER = 2
_ROLLBACK_STAGES = {"pre-stage", "forgejo-10", "current-forgejo"}


def _db_dump_estimate_bytes(inventory: DeploymentInventory) -> int:
    live_state_bytes = (
        inventory.repo_storage_bytes
        + inventory.attachments_bytes
        + inventory.lfs_bytes
        + inventory.actions_bytes
        + inventory.packages_bytes
    )
    return max(64 * 1024 * 1024, int(live_state_bytes * _DB_DUMP_OVERHEAD_RATIO))


def _build_integrity_checks(kind: str, source_path: str) -> tuple[IntegrityCheck, ...]:
    if kind == "database_dump":
        return (
            IntegrityCheck(
                name="pg_restore_list",
                command=f"pg_restore --list {source_path}",
                expectation="catalog can be listed without fatal errors",
            ),
        )
    return (
        IntegrityCheck(
            name="tar_listing",
            command=f"tar -tf {source_path}.tar",
            expectation="archive header can be listed without fatal errors",
        ),
    )


def generate_backup_manifest(
    inventory: DeploymentInventory,
    *,
    generated_at: datetime | None = None,
    maintenance_window: str = _DEFAULT_MAINTENANCE_WINDOW,
) -> BackupManifest:
    """Generate a deterministic backup manifest from audited deployment facts."""

    generated_at = generated_at or datetime.now(timezone.utc)

    artifacts = (
        BackupArtifact(
            artifact_id="postgresql-dump",
            kind="database_dump",
            source_path=f"/var/backups/{inventory.instance_name}/db/{inventory.database_name}.dump",
            capture_method=(
                f"pg_dump --format=custom --file <target> {inventory.database_name}"
            ),
            estimated_bytes=_db_dump_estimate_bytes(inventory),
            required_for_rollback=True,
            mutates_during_runtime=True,
            integrity_checks=_build_integrity_checks(
                "database_dump",
                f"/var/backups/{inventory.instance_name}/db/{inventory.database_name}.dump",
            ),
        ),
        BackupArtifact(
            artifact_id="gitea-config",
            kind="config_archive",
            source_path=inventory.config_path,
            capture_method="tar czf <target>.tar.gz <source>",
            estimated_bytes=2 * 1024 * 1024,
            required_for_rollback=True,
            mutates_during_runtime=False,
            integrity_checks=_build_integrity_checks("config_archive", inventory.config_path),
        ),
        BackupArtifact(
            artifact_id="gitea-custom",
            kind="filesystem_archive",
            source_path=inventory.custom_path,
            capture_method="tar czf <target>.tar.gz <source>",
            estimated_bytes=max(16 * 1024 * 1024, inventory.attachments_bytes // 20),
            required_for_rollback=True,
            mutates_during_runtime=False,
            integrity_checks=_build_integrity_checks("filesystem_archive", inventory.custom_path),
        ),
        BackupArtifact(
            artifact_id="gitea-data",
            kind="filesystem_archive",
            source_path=inventory.data_path,
            capture_method="tar czf <target>.tar.gz <source>",
            estimated_bytes=inventory.repo_storage_bytes + inventory.attachments_bytes,
            required_for_rollback=True,
            mutates_during_runtime=True,
            integrity_checks=_build_integrity_checks("filesystem_archive", inventory.data_path),
        ),
        BackupArtifact(
            artifact_id="gitea-lfs",
            kind="filesystem_archive",
            source_path=inventory.lfs_path,
            capture_method="tar czf <target>.tar.gz <source>",
            estimated_bytes=inventory.lfs_bytes,
            required_for_rollback=True,
            mutates_during_runtime=True,
            integrity_checks=_build_integrity_checks("filesystem_archive", inventory.lfs_path),
        ),
        BackupArtifact(
            artifact_id="gitea-logs",
            kind="filesystem_archive",
            source_path=inventory.log_path,
            capture_method="tar czf <target>.tar.gz <source>",
            estimated_bytes=max(8 * 1024 * 1024, inventory.work_dir_bytes // 50),
            required_for_rollback=False,
            mutates_during_runtime=True,
            integrity_checks=_build_integrity_checks("filesystem_archive", inventory.log_path),
        ),
    )

    estimated_backup_bytes = sum(artifact.estimated_bytes for artifact in artifacts)
    return BackupManifest(
        manifest_version=MANIFEST_VERSION,
        generated_at=generated_at.astimezone(timezone.utc),
        instance_name=inventory.instance_name,
        source_version=inventory.gitea_version,
        database_engine=inventory.database_engine,
        maintenance_window=maintenance_window,
        artifacts=artifacts,
        estimated_backup_bytes=estimated_backup_bytes,
        minimum_recommended_free_bytes=estimated_backup_bytes * _RECOMMENDED_FREE_SPACE_MULTIPLIER,
        rollback_checkpoint="hypervisor snapshot plus application-level backup set",
        notes=(
            "Take the VM snapshot immediately before stopping the service.",
            "Freeze writes before the final database dump for the cleanest rollback point.",
            "Do not attempt in-place downgrade after the current Forgejo stage; restore from backups instead.",
        ),
    )


def generate_rollback_plan(manifest: BackupManifest, *, stage: str) -> RollbackPlan:
    """Generate rollback steps for a migration stage validated by a manifest."""

    if stage not in _ROLLBACK_STAGES:
        valid_stages = ", ".join(sorted(_ROLLBACK_STAGES))
        raise ValueError(f"unsupported rollback stage {stage!r}; expected one of {valid_stages}")

    common_steps = (
        RollbackStep(1, "Stop Forgejo/Gitea service", "systemctl stop gitea forgejo"),
        RollbackStep(
            2,
            "Restore the pre-cutover binary or package set",
            "reinstall preserved Gitea package or binary from operator stash",
        ),
        RollbackStep(
            3,
            "Restore application configuration",
            "untar the gitea-config artifact over /etc/gitea",
        ),
        RollbackStep(
            4,
            "Restore application state directories",
            "untar gitea-custom, gitea-data, and gitea-lfs artifacts into /var/lib/gitea",
        ),
        RollbackStep(
            5,
            "Restore the PostgreSQL dump",
            "drop and recreate the target database, then pg_restore the custom dump",
            requires_full_restore=True,
        ),
        RollbackStep(
            6,
            "Start Gitea and run smoke checks",
            "systemctl start gitea && verify UI login, clone, and push paths",
        ),
    )

    if stage == "pre-stage":
        rationale = (
            "The migration has not committed schema changes yet; rollback should mainly rely "
            "on the VM snapshot, with application artifacts retained as a secondary checkpoint."
        )
        steps = common_steps[:2]
    elif stage == "forgejo-10":
        rationale = (
            "Rollback from the first Forgejo validation stage is still straightforward as long "
            "as the preserved Gitea package and full backup set are intact."
        )
        steps = common_steps
    else:
        rationale = (
            "After the current Forgejo stage, downgrade in place is unsafe. Treat rollback as a "
            "full restore from the pre-cutover manifest and VM snapshot."
        )
        steps = tuple(
            RollbackStep(
                order=step.order,
                summary=step.summary,
                command_hint=step.command_hint,
                requires_full_restore=True if step.order >= 3 else step.requires_full_restore,
            )
            for step in common_steps
        )

    return RollbackPlan(
        stage=stage,
        rationale=rationale,
        steps=steps,
        validated_with_manifest=manifest.manifest_version,
    )
