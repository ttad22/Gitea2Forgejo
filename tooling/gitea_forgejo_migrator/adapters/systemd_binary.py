from __future__ import annotations

from pathlib import Path
from typing import Any

from ..discovery import sh_quote
from ..models import BackupItem, BackupManifest, DeploymentAudit, SmokePlan
from ..releases import ForgejoRelease
from ..shell import ShellRunner
from .base import PlatformAdapter, RecordFn, RuntimeLayout, SmokeRunnerFn


class SystemdBinaryAdapter(PlatformAdapter):
    @property
    def adapter_name(self) -> str:
        return "systemd-binary-postgresql-nginx-host-sshd"

    def supports(self, audit: DeploymentAudit) -> bool:
        return (
            audit.service.install_mode.startswith("systemd")
            and audit.service.database == "postgresql"
            and audit.service.reverse_proxy == "nginx"
            and audit.service.ssh_mode == "host-sshd"
        )

    def validate(self, audit: DeploymentAudit) -> None:
        problems: list[str] = []
        if not audit.service.install_mode.startswith("systemd"):
            problems.append(f"unsupported install_mode={audit.service.install_mode}")
        if audit.service.database != "postgresql":
            problems.append(f"unsupported database={audit.service.database}")
        if audit.service.reverse_proxy != "nginx":
            problems.append(f"unsupported reverse_proxy={audit.service.reverse_proxy}")
        if audit.service.ssh_mode != "host-sshd":
            problems.append(f"unsupported ssh_mode={audit.service.ssh_mode}")
        if problems:
            raise RuntimeError("; ".join(problems))

    def detect_layout(self, runner: ShellRunner, audit: DeploymentAudit) -> RuntimeLayout:
        binary_path = runner.check("command -v gitea")
        arch = runner.check("uname -m")
        hostname = runner.check("hostname")
        database_name = self._note_value(audit, "database_name") or "gitea"
        return RuntimeLayout(
            binary_path=binary_path,
            binary_dir=str(Path(binary_path).parent),
            service_name=audit.service.app_service_name,
            database_name=database_name,
            reverse_proxy=audit.service.reverse_proxy,
            ssh_mode=audit.service.ssh_mode,
            arch=arch,
            hostname=hostname,
        )

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
        paths["backup_dir"].mkdir(parents=True, exist_ok=True)
        paths["release_dir"].mkdir(parents=True, exist_ok=True)
        runner.check(f"cp {sh_quote(layout.binary_path)} {sh_quote(str(paths['backup_dir'] / 'gitea-original.bin'))}")
        record(journal, paths["journal"], stage="backup", action="binary-copied")
        for item in backup_manifest.items:
            self._capture_backup_item(runner, item, layout, paths, journal, record)
        runner.check(f"systemctl cat {sh_quote(layout.service_name)} > {sh_quote(str(paths['backup_dir'] / 'service.unit'))}")
        record(journal, paths["journal"], stage="backup", action="filesystem-archived")

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
        release_dir = Path(paths["release_dir"]) / stage_name
        release_dir.mkdir(parents=True, exist_ok=True)
        binary_path = release_dir / release.asset_name
        record(journal, paths["journal"], stage=stage_name, action="download-start", url=release.asset_url)
        runner.check(f"curl -fsSL {sh_quote(release.asset_url)} -o {sh_quote(str(binary_path))}")
        runner.check(f"chmod 0755 {sh_quote(str(binary_path))}")
        self._verify_release_binary(runner, stage_name, release, binary_path, journal, paths["journal"], record)
        record(journal, paths["journal"], stage=stage_name, action="downloaded", release_path=str(binary_path))

        runner.check(f"systemctl stop {sh_quote(layout.service_name)}")
        record(journal, paths["journal"], stage=stage_name, action="service-stopped", service=layout.service_name)

        runner.check(f"install -m 0755 {sh_quote(str(binary_path))} {sh_quote(layout.binary_path)}")
        record(
            journal,
            paths["journal"],
            stage=stage_name,
            action="binary-replaced",
            binary_path=layout.binary_path,
            version=release.tag,
        )

        runner.check(f"systemctl start {sh_quote(layout.service_name)}")
        record(journal, paths["journal"], stage=stage_name, action="service-started", service=layout.service_name)

        runner.check("curl -fsS http://127.0.0.1:3000/api/health")
        record(journal, paths["journal"], stage=stage_name, action="healthcheck-passed")

        run_smoke_plan(smoke_plan, paths["journal"], journal, stage_name)

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
        try:
            record(journal, paths["journal"], stage="rollback", action="start")
            runner.run(f"systemctl stop {sh_quote(layout.service_name)}")
            runner.run(
                f"install -m 0755 {sh_quote(str(paths['backup_dir'] / 'gitea-original.bin'))} {sh_quote(layout.binary_path)}"
            )
            for item in backup_manifest.items:
                self._restore_backup_item(runner, item, layout, paths, journal, record)
            runner.run(f"systemctl start {sh_quote(layout.service_name)}")
            record(journal, paths["journal"], stage="rollback", action="completed")
            return True
        except Exception as exc:
            record(journal, paths["journal"], stage="rollback", action="failed", error=str(exc))
            return False

    @staticmethod
    def _note_value(audit: DeploymentAudit, key: str) -> str:
        prefix = f"{key}="
        for note in audit.notes:
            if note.startswith(prefix):
                return note[len(prefix) :].strip()
        return ""

    def _capture_backup_item(
        self,
        runner: ShellRunner,
        item: BackupItem,
        layout: RuntimeLayout,
        paths: dict[str, Path],
        journal: Any,
        record: RecordFn,
    ) -> None:
        if item.kind == "hypervisor_snapshot":
            record(
                journal,
                paths["journal"],
                stage="backup",
                action="hypervisor-snapshot-required",
                label=item.label,
                command=item.command or "",
            )
            return
        if item.kind == "database_dump":
            dump_path = self._backup_item_path(paths["backup_dir"], item)
            runner.check(f"sudo -u postgres pg_dump -Fc {sh_quote(layout.database_name)} > {sh_quote(str(dump_path))}")
            record(journal, paths["journal"], stage="backup", action="database-dumped", label=item.label)
            return
        if item.kind in {"file_archive", "directory_archive"}:
            archive_path = self._backup_item_path(paths["backup_dir"], item)
            if item.required:
                self._archive_path(runner, item.path or "", archive_path)
                record(
                    journal,
                    paths["journal"],
                    stage="backup",
                    action="path-archived",
                    label=item.label,
                    source_path=item.path or "",
                )
            else:
                if runner.run(f"test -e {sh_quote(item.path or '')}").returncode == 0:
                    self._archive_path(runner, item.path or "", archive_path)
                    record(
                        journal,
                        paths["journal"],
                        stage="backup",
                        action="path-archived",
                        label=item.label,
                        source_path=item.path or "",
                    )
                else:
                    record(
                        journal,
                        paths["journal"],
                        stage="backup",
                        action="optional-path-missing",
                        label=item.label,
                        source_path=item.path or "",
                    )
            return
        raise RuntimeError(f"unsupported backup item kind: {item.kind}")

    def _restore_backup_item(
        self,
        runner: ShellRunner,
        item: BackupItem,
        layout: RuntimeLayout,
        paths: dict[str, Path],
        journal: Any,
        record: RecordFn,
    ) -> None:
        if item.kind == "hypervisor_snapshot":
            return
        if item.kind == "database_dump":
            dump_path = self._backup_item_path(paths["backup_dir"], item)
            runner.run(
                f"sudo -u postgres dropdb --if-exists {sh_quote(layout.database_name)} && "
                f"sudo -u postgres createdb {sh_quote(layout.database_name)} && "
                f"sudo -u postgres pg_restore -d {sh_quote(layout.database_name)} {sh_quote(str(dump_path))}"
            )
            record(journal, paths["journal"], stage="rollback", action="database-restored", label=item.label)
            return
        if item.kind in {"file_archive", "directory_archive"}:
            archive_path = self._backup_item_path(paths["backup_dir"], item)
            if not archive_path.exists():
                if item.required:
                    raise RuntimeError(f"required backup archive missing for {item.label}: {archive_path}")
                return
            restore_parent = str(Path(item.path or "/").parent)
            runner.run(f"tar xzf {sh_quote(str(archive_path))} -C {sh_quote(restore_parent)}")
            record(
                journal,
                paths["journal"],
                stage="rollback",
                action="path-restored",
                label=item.label,
                source_path=item.path or "",
            )
            return
        raise RuntimeError(f"unsupported backup item kind: {item.kind}")

    def _archive_path(self, runner: ShellRunner, source: str, target: Path) -> None:
        source_path = Path(source)
        runner.check(f"tar czf {sh_quote(str(target))} -C {sh_quote(str(source_path.parent))} {sh_quote(source_path.name)}")

    def _verify_release_binary(
        self,
        runner: ShellRunner,
        stage_name: str,
        release: ForgejoRelease,
        binary_path: Path,
        journal: Any,
        journal_path: Path,
        record: RecordFn,
    ) -> None:
        if binary_path.name != release.asset_name:
            raise RuntimeError(f"{stage_name}: unexpected asset name {binary_path.name!r}")
        version_output = runner.check(f"{sh_quote(str(binary_path))} --version")
        expected_version = release.tag.lstrip("v")
        if "forgejo" not in version_output.lower() or expected_version not in version_output:
            raise RuntimeError(
                f"{stage_name}: downloaded binary version mismatch, expected {expected_version!r}, got {version_output!r}"
            )
        record(journal, journal_path, stage=stage_name, action="binary-verified", version_output=version_output.strip())

    @staticmethod
    def _backup_item_path(backup_dir: Path, item: BackupItem) -> Path:
        if item.kind == "database_dump":
            return backup_dir / f"{item.label}.dump"
        return backup_dir / f"{item.label}.tar.gz"
