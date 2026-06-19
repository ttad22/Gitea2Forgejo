from __future__ import annotations

from pathlib import PurePosixPath

from .models import BackupItem, BackupManifest, DeploymentAudit


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


def build_backup_manifest(audit: DeploymentAudit) -> BackupManifest:
    data_root = audit.data_root.rstrip("/")
    data_path = f"{data_root}/data"
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
            command="sudo -u postgres pg_dump -Fc gitea > gitea.pre-forgejo.dump",
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
    return BackupManifest(
        deployment_name=audit.name,
        backup_root_hint="/var/backups/gitea-forgejo-migrator",
        vm_snapshot_required=True,
        items=items,
    )
