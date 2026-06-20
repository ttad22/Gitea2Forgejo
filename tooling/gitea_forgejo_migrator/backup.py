from __future__ import annotations

import re
from pathlib import PurePosixPath

from .models import BackupItem, BackupManifest, DeploymentAudit, HostArtifact


def _note_value(audit: DeploymentAudit, key: str) -> str:
    prefix = f"{key}="
    for note in audit.notes:
        if note.startswith(prefix):
            return note[len(prefix) :].strip()
    return ""


def _add_unique_path_item(
    items: list[BackupItem],
    seen_paths: set[str],
    *,
    label: str,
    kind: str,
    path: str,
    required: bool = True,
) -> None:
    normalized = path.strip()
    if not normalized or normalized in seen_paths:
        return
    seen_paths.add(normalized)
    items.append(BackupItem(label=label, kind=kind, path=normalized, required=required))


def _is_within(path: str, parent: str) -> bool:
    try:
        PurePosixPath(path).relative_to(PurePosixPath(parent))
        return True
    except ValueError:
        return False


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug or "path"


def _discovered_preserve_paths(audit: DeploymentAudit) -> list[tuple[str, str, str]]:
    discovered: list[tuple[str, str, str]] = []
    prefix = "preserve_path:"
    for note in audit.notes:
        if not note.startswith(prefix):
            continue
        payload = note[len(prefix) :]
        try:
            kind, remainder = payload.split(":", 1)
            key, path = remainder.split("=", 1)
        except ValueError:
            continue
        discovered.append((kind.strip(), key.strip(), path.strip()))
    return discovered


def _artifact_backup_items(audit: DeploymentAudit) -> list[BackupItem]:
    items: list[BackupItem] = []
    seen_paths: set[str] = set()
    allowed_decisions = {"adopted", "preserved_external", "manual_review"}
    kind_map = {
        "file": "file_archive",
        "directory": "directory_archive",
        "hook": "file_archive",
        "script": "file_archive",
        "dropin": "file_archive",
    }
    for artifact in audit.host_artifacts:
        if not artifact.path or artifact.decision not in allowed_decisions:
            continue
        archive_kind = kind_map.get(artifact.kind)
        if not archive_kind:
            continue
        normalized = artifact.path.strip()
        if not normalized or normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        items.append(
            BackupItem(
                label=f"artifact_{_slug(artifact.artifact_id)}",
                kind=archive_kind,
                path=normalized,
                required=artifact.required,
            )
        )
    return items


def build_backup_manifest(audit: DeploymentAudit) -> BackupManifest:
    data_root = audit.data_root.rstrip("/")
    data_path = f"{data_root}/data"
    database_name = _note_value(audit, "database_name") or "gitea"
    repository_root = _note_value(audit, "repository_root") or f"{data_root}/data/gitea-repositories"
    attachments_path = _note_value(audit, "attachments_path") or f"{data_root}/data/attachments"
    packages_path = _note_value(audit, "packages_path") or f"{data_root}/data/packages"
    ssh_authorized_keys_file = _note_value(audit, "ssh_authorized_keys_file")
    lfs_enabled = _note_value(audit, "lfs_start_server").lower() == "true"

    items = [
        BackupItem(
            label="vm_snapshot",
            kind="hypervisor_snapshot",
            command="Create hypervisor snapshot before service replacement.",
        ),
        BackupItem(
            label="postgres_dump",
            kind="database_dump",
            command=f"sudo -u postgres pg_dump -Fc {database_name} > {database_name}.pre-forgejo.dump",
        ),
        BackupItem(
            label="app_ini",
            kind="file_archive",
            path=audit.app_ini_path,
        ),
        BackupItem(
            label="custom",
            kind="directory_archive",
            path=f"{data_root}/custom",
        ),
        BackupItem(
            label="data",
            kind="directory_archive",
            path=data_path,
        ),
    ]
    seen_paths = {
        audit.app_ini_path,
        f"{data_root}/custom",
        data_path,
    }
    if not _is_within(repository_root, data_path):
        _add_unique_path_item(
            items,
            seen_paths,
            label="repository_root",
            kind="directory_archive",
            path=repository_root,
        )
    if not _is_within(attachments_path, data_path):
        _add_unique_path_item(
            items,
            seen_paths,
            label="attachments",
            kind="directory_archive",
            path=attachments_path,
        )
    _add_unique_path_item(
        items,
        seen_paths,
        label="lfs",
        kind="directory_archive",
        path=f"{data_root}/lfs",
        required=lfs_enabled or audit.features.lfs_objects > 0 or audit.resources.lfs_mb > 0,
    )
    if not _is_within(packages_path, data_path):
        _add_unique_path_item(
            items,
            seen_paths,
            label="packages",
            kind="directory_archive",
            path=packages_path,
            required=False,
        )
    _add_unique_path_item(
        items,
        seen_paths,
        label="ssh_authorized_keys",
        kind="file_archive",
        path=ssh_authorized_keys_file,
    )
    _add_unique_path_item(
        items,
        seen_paths,
        label="log",
        kind="directory_archive",
        path=f"{data_root}/log",
        required=False,
    )
    for kind, key, path in _discovered_preserve_paths(audit):
        label = f"config_{_slug(key)}"
        archive_kind = "directory_archive" if kind == "directory" else "file_archive"
        _add_unique_path_item(
            items,
            seen_paths,
            label=label,
            kind=archive_kind,
            path=path,
            required=False,
        )
    for item in _artifact_backup_items(audit):
        _add_unique_path_item(
            items,
            seen_paths,
            label=item.label,
            kind=item.kind,
            path=item.path or "",
            required=item.required,
        )
    return BackupManifest(
        deployment_name=audit.name,
        backup_root_hint="/var/backups/gitea-forgejo-migrator",
        vm_snapshot_required=True,
        items=items,
    )
