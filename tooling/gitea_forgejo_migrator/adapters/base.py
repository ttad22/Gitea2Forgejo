from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..models import BackupManifest, DeploymentAudit, SmokePlan
from ..releases import ForgejoRelease
from ..shell import ShellRunner


@dataclass(frozen=True, slots=True)
class RuntimeLayout:
    binary_path: str
    binary_dir: str
    service_name: str
    database_name: str
    reverse_proxy: str
    ssh_mode: str
    arch: str
    hostname: str


RecordFn = Callable[..., None]
SmokeRunnerFn = Callable[[SmokePlan, Path, Any, str], None]


class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def adapter_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def supports(self, audit: DeploymentAudit) -> bool:
        raise NotImplementedError

    @abstractmethod
    def validate(self, audit: DeploymentAudit) -> None:
        raise NotImplementedError

    @abstractmethod
    def detect_layout(self, runner: ShellRunner, audit: DeploymentAudit) -> RuntimeLayout:
        raise NotImplementedError

    @abstractmethod
    def backup(
        self,
        *,
        runner: ShellRunner,
        audit: DeploymentAudit,
        layout: RuntimeLayout,
        paths: dict[str, Path],
        backup_manifest: BackupManifest,
        journal: Any,
        record: RecordFn,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def install_release(
        self,
        *,
        runner: ShellRunner,
        stage_name: str,
        release: ForgejoRelease,
        layout: RuntimeLayout,
        audit: DeploymentAudit,
        paths: dict[str, Path],
        smoke_plan: SmokePlan,
        journal: Any,
        record: RecordFn,
        run_smoke_plan: SmokeRunnerFn,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(
        self,
        *,
        runner: ShellRunner,
        layout: RuntimeLayout,
        audit: DeploymentAudit,
        paths: dict[str, Path],
        backup_manifest: BackupManifest,
        journal: Any,
        record: RecordFn,
    ) -> bool:
        raise NotImplementedError
