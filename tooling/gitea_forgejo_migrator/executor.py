from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import PlatformAdapter, PlatformAdapterRegistry, RuntimeLayout, SystemdBinaryAdapter
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

class MigrationExecutor:
    def __init__(
        self,
        *,
        runner: ShellRunner | None = None,
        adapter: PlatformAdapter | None = None,
        adapter_registry: PlatformAdapterRegistry | None = None,
        release_resolver: ReleaseResolver | None = None,
    ) -> None:
        self.runner = runner or ShellRunner()
        self.adapter_registry = adapter_registry or PlatformAdapterRegistry()
        self.adapter = adapter
        self.release_resolver = release_resolver or ReleaseResolver()

    def migrate(self, request: MigrationRequest) -> MigrationOutcome:
        if os.geteuid() != 0 and not request.dry_run:
            raise RuntimeError("migrate requires root privileges unless --dry-run is used.")

        audit = collect_live_audit(self.runner, app_ini_path=request.app_ini_path, data_root=request.data_root)
        adapter = self.adapter or self.adapter_registry.resolve(audit)
        adapter.validate(audit)
        readiness = evaluate_deployment(_report_from_audit(audit))
        compatibility = assess_gitea_to_forgejo(audit.gitea_version)
        if not readiness.ready and not request.force:
            raise RuntimeError(f"migration blocked by readiness findings: {readiness.risk_level}")

        layout = adapter.detect_layout(self.runner, audit)
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
            adapter.backup(
                runner=self.runner,
                audit=audit,
                layout=layout,
                paths=paths,
                backup_manifest=backup_manifest,
                journal=journal,
                record=self._record,
            )
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

            adapter.install_release(
                runner=self.runner,
                stage_name="forgejo-10",
                release=releases.forgejo_10,
                layout=layout,
                audit=audit,
                paths=paths,
                smoke_plan=smoke_plan,
                journal=journal,
                record=self._record,
                run_smoke_plan=self._run_smoke_plan,
            )
            stages_completed.append("forgejo-10")
            self._record(journal, paths["journal"], stage="forgejo-10", action="completed", version=releases.forgejo_10.tag)

            adapter.install_release(
                runner=self.runner,
                stage_name="forgejo-current",
                release=releases.forgejo_current,
                layout=layout,
                audit=audit,
                paths=paths,
                smoke_plan=smoke_plan,
                journal=journal,
                record=self._record,
                run_smoke_plan=self._run_smoke_plan,
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
                rolled_back = adapter.rollback(
                    runner=self.runner,
                    layout=layout,
                    audit=audit,
                    paths=paths,
                    backup_manifest=backup_manifest,
                    journal=journal,
                    record=self._record,
                )
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
