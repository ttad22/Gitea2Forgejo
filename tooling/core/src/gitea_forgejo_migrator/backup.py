from __future__ import annotations

from .models import BackupItem, BackupManifest, DeploymentAudit


def build_backup_manifest(audit: DeploymentAudit) -> BackupManifest:
    data_root = audit.data_root.rstrip("/")
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
        BackupItem(label="app_ini", kind="file_archive", path=audit.app_ini_path),
        BackupItem(label="custom", kind="directory_archive", path=f"{data_root}/custom"),
        BackupItem(label="data", kind="directory_archive", path=f"{data_root}/data"),
        BackupItem(label="lfs", kind="directory_archive", path=f"{data_root}/lfs"),
        BackupItem(label="log", kind="directory_archive", path=f"{data_root}/log", required=False),
    ]
    return BackupManifest(
        deployment_name=audit.name,
        backup_root_hint="/var/backups/gitea-forgejo-migrator",
        vm_snapshot_required=True,
        items=items,
    )
