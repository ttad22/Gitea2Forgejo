from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _normalize_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_int(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return value


def _normalize_float(value: Any, field_name: str, *, minimum: float = 0.0) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    normalized = float(value)
    if normalized < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return normalized


def _normalize_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


@dataclass(frozen=True)
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

    @property
    def total_data_mb(self) -> float:
        return self.repository_storage_mb + self.attachments_storage_mb

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeploymentAuditReport":
        return cls(
            host_label=_normalize_string(payload["host_label"], "host_label"),
            service_model=_normalize_string(payload["service_model"], "service_model").lower(),
            gitea_version=_normalize_string(payload["gitea_version"], "gitea_version"),
            database_backend=_normalize_string(payload["database_backend"], "database_backend").lower(),
            database_version=_normalize_string(payload["database_version"], "database_version"),
            config_path=_normalize_string(payload["config_path"], "config_path"),
            data_root=_normalize_string(payload["data_root"], "data_root"),
            reverse_proxy=_normalize_string(payload["reverse_proxy"], "reverse_proxy").lower(),
            reverse_proxy_port=_normalize_int(payload["reverse_proxy_port"], "reverse_proxy_port", minimum=1),
            app_port=_normalize_int(payload["app_port"], "app_port", minimum=1),
            repositories=_normalize_int(payload["repositories"], "repositories"),
            users=_normalize_int(payload["users"], "users"),
            org_memberships=_normalize_int(payload["org_memberships"], "org_memberships"),
            repository_storage_mb=_normalize_float(payload["repository_storage_mb"], "repository_storage_mb"),
            attachments_storage_mb=_normalize_float(payload["attachments_storage_mb"], "attachments_storage_mb"),
            lfs_objects=_normalize_int(payload["lfs_objects"], "lfs_objects"),
            actions_runs=_normalize_int(payload["actions_runs"], "actions_runs"),
            action_runners=_normalize_int(payload["action_runners"], "action_runners"),
            packages=_normalize_int(payload["packages"], "packages"),
            root_free_gb=_normalize_float(payload["root_free_gb"], "root_free_gb"),
            internal_ssh_server=_normalize_bool(payload["internal_ssh_server"], "internal_ssh_server"),
            lfs_enabled=_normalize_bool(payload["lfs_enabled"], "lfs_enabled"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "host_label": self.host_label,
            "service_model": self.service_model,
            "gitea_version": self.gitea_version,
            "database_backend": self.database_backend,
            "database_version": self.database_version,
            "config_path": self.config_path,
            "data_root": self.data_root,
            "reverse_proxy": self.reverse_proxy,
            "reverse_proxy_port": self.reverse_proxy_port,
            "app_port": self.app_port,
            "repositories": self.repositories,
            "users": self.users,
            "org_memberships": self.org_memberships,
            "repository_storage_mb": self.repository_storage_mb,
            "attachments_storage_mb": self.attachments_storage_mb,
            "lfs_objects": self.lfs_objects,
            "actions_runs": self.actions_runs,
            "action_runners": self.action_runners,
            "packages": self.packages,
            "root_free_gb": self.root_free_gb,
            "internal_ssh_server": self.internal_ssh_server,
            "lfs_enabled": self.lfs_enabled,
        }
