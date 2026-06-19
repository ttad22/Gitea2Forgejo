from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import evaluate_deployment
from .backup import build_backup_manifest
from .compatibility import assess_gitea_to_forgejo
from .discovery import collect_live_audit, sh_quote
from .io import dump_backup_manifest, dump_json, dump_migration_plan, dump_smoke_script
from .journal import Journal
from .models import BackupItem, BackupManifest, CompatibilityAssessment, DeploymentAudit, MigrationPlan, SmokePlan
from .planning import build_migration_plan
from .preflight import _report_from_audit
from .releases import ForgejoRelease, ReleaseBundle, ReleaseResolver
from .shell import ShellRunner
from .smoke import build_smoke_plan


@dataclass(frozen=True, slots=True)
class MigrationRequest:
    app_ini_path: str = "/etc/gitea/app.ini"
    data_root: str = "/var/lib/gitea"
    work_root: str = "/var/backups/gitea-forgejo-migrator/runs"
    force: bool = False
    dry_run: bool = False
    forgejo_10_url: str | None = None
    forgejo_current_url: str | None = None


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


@dataclass(frozen=True, slots=True)
class MigrationOutcome:
    success: bool
    rollback_performed: bool
    work_dir: str
    journal_path: str
    audit_path: str
    plan_path: str
    backup_manifest_path: str
    smoke_script_path: str
    outcome_path: str
    stages_completed: tuple[str, ...]
    compatibility: CompatibilityAssessment
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SupportedCohortAdapter:
    @staticmethod
    def _note_value(audit: DeploymentAudit, key: str) -> str:
        prefix = f"{key}="
        for note in audit.notes:
            if note.startswith(prefix):
                return note[len(prefix) :].strip()
        return ""

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
        compatibility = assess_gitea_to_forgejo(audit.gitea_version)
        if not compatibility.supported:
            problems.append(compatibility.reason)
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


class MigrationExecutor:
    def __init__(
        self,
        *,
        runner: ShellRunner | None = None,
        adapter: SupportedCohortAdapter | None = None,
        release_resolver: ReleaseResolver | None = None,
    ) -> None:
        self.runner = runner or ShellRunner()
        self.adapter = adapter or SupportedCohortAdapter()
        self.release_resolver = release_resolver or ReleaseResolver()

    def migrate(self, request: MigrationRequest) -> MigrationOutcome:
        if os.geteuid() != 0 and not request.dry_run:
            raise RuntimeError("migrate requires root privileges unless --dry-run is used.")

        audit = collect_live_audit(self.runner, app_ini_path=request.app_ini_path, data_root=request.data_root)
        self.adapter.validate(audit)
        readiness = evaluate_deployment(_report_from_audit(audit))
        compatibility = assess_gitea_to_forgejo(audit.gitea_version)
        if not readiness.ready and not request.force:
            raise RuntimeError(f"migration blocked by readiness findings: {readiness.risk_level}")

        layout = self.adapter.detect_layout(self.runner, audit)
        releases = self._resolve_releases(request)
        smoke_plan = build_smoke_plan(audit)
        migration_plan = build_migration_plan(audit)
        backup_manifest = build_backup_manifest(audit)

        work_dir = Path(request.work_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        journal = Journal.empty()
        stages_completed: list[str] = []
        rolled_back = False

        self._ensure_dir(work_dir)
        paths = self._artifact_paths(work_dir)
        dump_json(paths["audit"], audit.to_dict())
        dump_json(paths["readiness"], readiness.to_dict())
        dump_backup_manifest(paths["backup"], backup_manifest)
        dump_migration_plan(paths["plan"], migration_plan)
        dump_smoke_script(paths["smoke"], smoke_plan)

        self._record(journal, paths["journal"], stage="init", action="artifacts-written", work_dir=str(work_dir))

        try:
            self._backup(audit, layout, request, paths, backup_manifest, journal)
            stages_completed.append("backup")
            self._record(journal, paths["journal"], stage="backup", action="completed")

            if request.dry_run:
                message = "Dry run completed. No mutation commands were executed."
                outcome = self._finalize_outcome(
                    success=True,
                    rollback_performed=False,
                    paths=paths,
                    stages_completed=tuple(stages_completed),
                    compatibility=compatibility,
                    message=message,
                )
                dump_json(paths["outcome"], outcome.to_dict())
                return outcome

            self._stage_release("forgejo-10", releases.forgejo_10, layout, audit, request, paths, smoke_plan, journal)
            stages_completed.append("forgejo-10")
            self._record(journal, paths["journal"], stage="forgejo-10", action="completed", version=releases.forgejo_10.tag)

            self._stage_release(
                "forgejo-current",
                releases.forgejo_current,
                layout,
                audit,
                request,
                paths,
                smoke_plan,
                journal,
            )
            stages_completed.append("forgejo-current")
            self._record(
                journal,
                paths["journal"],
                stage="forgejo-current",
                action="completed",
                version=releases.forgejo_current.tag,
            )

            outcome = self._finalize_outcome(
                success=True,
                rollback_performed=False,
                paths=paths,
                stages_completed=tuple(stages_completed),
                compatibility=compatibility,
                message="Migration completed successfully.",
            )
            dump_json(paths["outcome"], outcome.to_dict())
            return outcome
        except Exception as exc:
            self._record(journal, paths["journal"], stage="failure", action="captured", error=str(exc))
            if not request.dry_run:
                rolled_back = self._rollback(layout, audit, request, paths, backup_manifest, journal)
            outcome = self._finalize_outcome(
                success=False,
                rollback_performed=rolled_back,
                paths=paths,
                stages_completed=tuple(stages_completed),
                compatibility=compatibility,
                message=str(exc),
            )
            dump_json(paths["outcome"], outcome.to_dict())
            raise RuntimeError(json.dumps(outcome.to_dict(), indent=2))

    def _resolve_releases(self, request: MigrationRequest) -> ReleaseBundle:
        bundle = self.release_resolver.resolve()
        forgejo_10 = (
            ForgejoRelease(tag=bundle.forgejo_10.tag, asset_name=bundle.forgejo_10.asset_name, asset_url=request.forgejo_10_url)
            if request.forgejo_10_url
            else bundle.forgejo_10
        )
        forgejo_current = (
            ForgejoRelease(
                tag=bundle.forgejo_current.tag,
                asset_name=bundle.forgejo_current.asset_name,
                asset_url=request.forgejo_current_url,
            )
            if request.forgejo_current_url
            else bundle.forgejo_current
        )
        return ReleaseBundle(forgejo_10=forgejo_10, forgejo_current=forgejo_current)

    def _stage_release(
        self,
        stage_name: str,
        release: ForgejoRelease,
        layout: RuntimeLayout,
        audit: DeploymentAudit,
        request: MigrationRequest,
        paths: dict[str, Path],
        smoke_plan: SmokePlan,
        journal: Journal,
    ) -> None:
        release_dir = Path(paths["release_dir"]) / stage_name
        self._ensure_dir(release_dir)
        binary_path = release_dir / release.asset_name
        self._record(journal, paths["journal"], stage=stage_name, action="download-start", url=release.asset_url)
        self.runner.check(f"curl -fsSL {sh_quote(release.asset_url)} -o {sh_quote(str(binary_path))}")
        self.runner.check(f"chmod 0755 {sh_quote(str(binary_path))}")
        self._verify_release_binary(stage_name, release, binary_path, journal, paths["journal"])
        self._record(journal, paths["journal"], stage=stage_name, action="downloaded", release_path=str(binary_path))

        self.runner.check(f"systemctl stop {sh_quote(layout.service_name)}")
        self._record(journal, paths["journal"], stage=stage_name, action="service-stopped", service=layout.service_name)

        self.runner.check(f"install -m 0755 {sh_quote(str(binary_path))} {sh_quote(layout.binary_path)}")
        self._record(
            journal,
            paths["journal"],
            stage=stage_name,
            action="binary-replaced",
            binary_path=layout.binary_path,
            version=release.tag,
        )

        self.runner.check(f"systemctl start {sh_quote(layout.service_name)}")
        self._record(journal, paths["journal"], stage=stage_name, action="service-started", service=layout.service_name)

        self.runner.check("curl -fsS http://127.0.0.1:3000/api/health")
        self._record(journal, paths["journal"], stage=stage_name, action="healthcheck-passed")

        self._run_smoke_plan(smoke_plan, paths["journal"], journal, stage_name)

    def _run_smoke_plan(self, smoke_plan: SmokePlan, journal_path: Path, journal: Journal, stage_name: str) -> None:
        for check in smoke_plan.checks:
            result = self.runner.run(check.command)
            if result.returncode == 0:
                self._record(journal, journal_path, stage=stage_name, action="smoke-passed", check=check.name)
                continue
            if check.critical:
                self._record(
                    journal,
                    journal_path,
                    stage=stage_name,
                    action="smoke-failed",
                    check=check.name,
                    stderr=result.stderr.strip(),
                )
                raise RuntimeError(f"critical smoke check failed: {check.name}")
            self._record(
                journal,
                journal_path,
                stage=stage_name,
                action="smoke-optional-failed",
                check=check.name,
                stderr=result.stderr.strip(),
            )

    def _backup(
        self,
        audit: DeploymentAudit,
        layout: RuntimeLayout,
        request: MigrationRequest,
        paths: dict[str, Path],
        backup_manifest: BackupManifest,
        journal: Journal,
    ) -> None:
        self._ensure_dir(paths["backup_dir"])
        self._ensure_dir(paths["release_dir"])
        self.runner.check(f"cp {sh_quote(layout.binary_path)} {sh_quote(str(paths['backup_dir'] / 'gitea-original.bin'))}")
        self._record(journal, paths["journal"], stage="backup", action="binary-copied")
        for item in backup_manifest.items:
            self._capture_backup_item(item, layout, paths, journal)
        self.runner.check(f"systemctl cat {sh_quote(layout.service_name)} > {sh_quote(str(paths['backup_dir'] / 'service.unit'))}")
        self._record(journal, paths["journal"], stage="backup", action="filesystem-archived")

    def _capture_backup_item(
        self,
        item: BackupItem,
        layout: RuntimeLayout,
        paths: dict[str, Path],
        journal: Journal,
    ) -> None:
        if item.kind == "hypervisor_snapshot":
            self._record(
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
            self.runner.check(
                f"sudo -u postgres pg_dump -Fc {sh_quote(layout.database_name)} > {sh_quote(str(dump_path))}"
            )
            self._record(journal, paths["journal"], stage="backup", action="database-dumped", label=item.label)
            return
        if item.kind in {"file_archive", "directory_archive"}:
            archive_path = self._backup_item_path(paths["backup_dir"], item)
            if item.required:
                self._archive_path(item.path or "", archive_path)
                self._record(
                    journal,
                    paths["journal"],
                    stage="backup",
                    action="path-archived",
                    label=item.label,
                    source_path=item.path or "",
                )
            else:
                if self.runner.run(f"test -e {sh_quote(item.path or '')}").returncode == 0:
                    self._archive_path(item.path or "", archive_path)
                    self._record(
                        journal,
                        paths["journal"],
                        stage="backup",
                        action="path-archived",
                        label=item.label,
                        source_path=item.path or "",
                    )
                else:
                    self._record(
                        journal,
                        paths["journal"],
                        stage="backup",
                        action="optional-path-missing",
                        label=item.label,
                        source_path=item.path or "",
                    )
            return
        raise RuntimeError(f"unsupported backup item kind: {item.kind}")

    def _archive_path(self, source: str, target: Path) -> None:
        source_path = Path(source)
        parent = source_path.parent
        name = source_path.name
        self.runner.check(
            f"tar czf {sh_quote(str(target))} -C {sh_quote(str(parent))} {sh_quote(name)}"
        )

    def _verify_release_binary(
        self,
        stage_name: str,
        release: ForgejoRelease,
        binary_path: Path,
        journal: Journal,
        journal_path: Path,
    ) -> None:
        if binary_path.name != release.asset_name:
            raise RuntimeError(f"{stage_name}: unexpected asset name {binary_path.name!r}")
        version_output = self.runner.check(f"{sh_quote(str(binary_path))} --version")
        expected_version = release.tag.lstrip("v")
        if "forgejo" not in version_output.lower() or expected_version not in version_output:
            raise RuntimeError(
                f"{stage_name}: downloaded binary version mismatch, expected {expected_version!r}, got {version_output!r}"
            )
        self._record(
            journal,
            journal_path,
            stage=stage_name,
            action="binary-verified",
            version_output=version_output.strip(),
        )

    def _rollback(
        self,
        layout: RuntimeLayout,
        audit: DeploymentAudit,
        request: MigrationRequest,
        paths: dict[str, Path],
        backup_manifest: BackupManifest,
        journal: Journal,
    ) -> bool:
        try:
            self._record(journal, paths["journal"], stage="rollback", action="start")
            self.runner.run(f"systemctl stop {sh_quote(layout.service_name)}")
            self.runner.run(
                f"install -m 0755 {sh_quote(str(paths['backup_dir'] / 'gitea-original.bin'))} {sh_quote(layout.binary_path)}"
            )
            for item in backup_manifest.items:
                self._restore_backup_item(item, layout, paths, journal)
            self.runner.run(f"systemctl start {sh_quote(layout.service_name)}")
            self._record(journal, paths["journal"], stage="rollback", action="completed")
            return True
        except Exception as exc:
            self._record(journal, paths["journal"], stage="rollback", action="failed", error=str(exc))
            return False

    def _restore_backup_item(
        self,
        item: BackupItem,
        layout: RuntimeLayout,
        paths: dict[str, Path],
        journal: Journal,
    ) -> None:
        if item.kind == "hypervisor_snapshot":
            return
        if item.kind == "database_dump":
            dump_path = self._backup_item_path(paths["backup_dir"], item)
            self.runner.run(
                f"sudo -u postgres dropdb --if-exists {sh_quote(layout.database_name)} && "
                f"sudo -u postgres createdb {sh_quote(layout.database_name)} && "
                f"sudo -u postgres pg_restore -d {sh_quote(layout.database_name)} {sh_quote(str(dump_path))}"
            )
            self._record(journal, paths["journal"], stage="rollback", action="database-restored", label=item.label)
            return
        if item.kind in {"file_archive", "directory_archive"}:
            archive_path = self._backup_item_path(paths["backup_dir"], item)
            if not archive_path.exists():
                if item.required:
                    raise RuntimeError(f"required backup archive missing for {item.label}: {archive_path}")
                return
            restore_parent = str(Path(item.path or "/").parent)
            self.runner.run(f"tar xzf {sh_quote(str(archive_path))} -C {sh_quote(restore_parent)}")
            self._record(
                journal,
                paths["journal"],
                stage="rollback",
                action="path-restored",
                label=item.label,
                source_path=item.path or "",
            )
            return
        raise RuntimeError(f"unsupported backup item kind: {item.kind}")

    def _backup_item_path(self, backup_dir: Path, item: BackupItem) -> Path:
        if item.kind == "database_dump":
            return backup_dir / f"{item.label}.dump"
        return backup_dir / f"{item.label}.tar.gz"

    def _artifact_paths(self, work_dir: Path) -> dict[str, Path]:
        return {
            "audit": work_dir / "audit.json",
            "readiness": work_dir / "readiness.json",
            "backup": work_dir / "backup-manifest.json",
            "plan": work_dir / "migration-plan.json",
            "smoke": work_dir / "smoke.sh",
            "outcome": work_dir / "outcome.json",
            "journal": work_dir / "journal.json",
            "backup_dir": work_dir / "backup",
            "release_dir": work_dir / "releases",
        }

    def _finalize_outcome(
        self,
        *,
        success: bool,
        rollback_performed: bool,
        paths: dict[str, Path],
        stages_completed: tuple[str, ...],
        compatibility: CompatibilityAssessment,
        message: str,
    ) -> MigrationOutcome:
        return MigrationOutcome(
            success=success,
            rollback_performed=rollback_performed,
            work_dir=str(Path(paths["audit"]).parent),
            journal_path=str(paths["journal"]),
            audit_path=str(paths["audit"]),
            plan_path=str(paths["plan"]),
            backup_manifest_path=str(paths["backup"]),
            smoke_script_path=str(paths["smoke"]),
            outcome_path=str(paths["outcome"]),
            stages_completed=stages_completed,
            compatibility=compatibility,
            message=message,
        )

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _record(self, journal: Journal, path: Path, *, stage: str, action: str, **metadata: Any) -> None:
        journal.record(stage=stage, action=action, **metadata)
        journal.dump(path)
