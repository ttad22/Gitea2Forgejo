from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tooling.backup import DeploymentInventory, generate_backup_manifest, generate_rollback_plan


@pytest.fixture()
def inventory() -> DeploymentInventory:
    return DeploymentInventory(
        instance_name="git-example",
        hostname="git-ops",
        service_name="gitea",
        gitea_version="1.22.0",
        database_engine="postgresql",
        database_name="gitea",
        config_path="/etc/gitea/app.ini",
        work_path="/var/lib/gitea",
        data_path="/var/lib/gitea/data",
        custom_path="/var/lib/gitea/custom",
        lfs_path="/var/lib/gitea/lfs",
        log_path="/var/lib/gitea/log",
        repo_storage_path="/var/lib/gitea/data/gitea-repositories",
        attachments_path="/var/lib/gitea/data/attachments",
        root_free_bytes=188 * 1024 * 1024 * 1024,
        work_dir_bytes=876 * 1024 * 1024,
        repo_storage_bytes=795 * 1024 * 1024,
        attachments_bytes=80 * 1024 * 1024,
        lfs_bytes=0,
    )


def test_generate_backup_manifest_is_deterministic(inventory: DeploymentInventory) -> None:
    generated_at = datetime(2026, 6, 18, 14, 30, tzinfo=timezone.utc)

    manifest = generate_backup_manifest(inventory, generated_at=generated_at)

    assert manifest.manifest_version == "2026-06-18"
    assert manifest.generated_at == generated_at
    assert manifest.instance_name == "git-example"
    assert manifest.artifact_ids() == (
        "postgresql-dump",
        "gitea-config",
        "gitea-custom",
        "gitea-data",
        "gitea-lfs",
        "gitea-logs",
    )
    assert manifest.estimated_backup_bytes == sum(
        artifact.estimated_bytes for artifact in manifest.artifacts
    )
    assert manifest.minimum_recommended_free_bytes == manifest.estimated_backup_bytes * 2


def test_manifest_serialization_exposes_iso8601_timestamp(inventory: DeploymentInventory) -> None:
    manifest = generate_backup_manifest(
        inventory,
        generated_at=datetime(2026, 6, 18, 16, 0, tzinfo=timezone.utc),
    )

    payload = manifest.to_dict()

    assert payload["generated_at"] == "2026-06-18T16:00:00+00:00"
    assert payload["artifacts"][0]["artifact_id"] == "postgresql-dump"
    assert payload["artifacts"][0]["integrity_checks"][0]["name"] == "pg_restore_list"


def test_db_dump_estimate_has_floor_for_small_instances() -> None:
    inventory = DeploymentInventory(
        instance_name="tiny",
        hostname="tiny-host",
        service_name="gitea",
        gitea_version="1.22.0",
        database_engine="postgresql",
        database_name="gitea",
        config_path="/etc/gitea/app.ini",
        work_path="/var/lib/gitea",
        data_path="/var/lib/gitea/data",
        custom_path="/var/lib/gitea/custom",
        lfs_path="/var/lib/gitea/lfs",
        log_path="/var/lib/gitea/log",
        repo_storage_path="/var/lib/gitea/data/gitea-repositories",
        attachments_path="/var/lib/gitea/data/attachments",
        root_free_bytes=10 * 1024 * 1024 * 1024,
        work_dir_bytes=128 * 1024 * 1024,
        repo_storage_bytes=10 * 1024 * 1024,
        attachments_bytes=2 * 1024 * 1024,
        lfs_bytes=0,
    )

    manifest = generate_backup_manifest(inventory)

    assert manifest.artifacts[0].estimated_bytes == 64 * 1024 * 1024


def test_generate_rollback_plan_marks_full_restore_for_final_stage(
    inventory: DeploymentInventory,
) -> None:
    manifest = generate_backup_manifest(inventory)

    rollback_plan = generate_rollback_plan(manifest, stage="current-forgejo")

    assert rollback_plan.stage == "current-forgejo"
    assert rollback_plan.validated_with_manifest == manifest.manifest_version
    assert any(step.requires_full_restore for step in rollback_plan.steps if step.order >= 3)
    assert "full restore" in rollback_plan.rationale


def test_inventory_requires_absolute_paths(inventory: DeploymentInventory) -> None:
    with pytest.raises(ValueError, match="absolute path"):
        DeploymentInventory(
            **{
                **inventory.__dict__,
                "config_path": "etc/gitea/app.ini",
            }
        )


def test_generate_rollback_plan_rejects_unknown_stage(
    inventory: DeploymentInventory,
) -> None:
    manifest = generate_backup_manifest(inventory)

    with pytest.raises(ValueError, match="unsupported rollback stage"):
        generate_rollback_plan(manifest, stage="latest")
