from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import evaluate_deployment
from .backup import build_backup_manifest
from .compatibility import assess_gitea_to_forgejo
from .discovery import collect_live_audit
from .io import dump_backup_manifest, dump_json, dump_migration_plan, dump_smoke_script, load_audit
from .models import DeploymentAuditReport
from .planning import build_migration_plan
from .shell import ShellRunner
from .simulate import build_simulation_report
from .smoke import build_smoke_plan


def _compatibility_cmd(args: argparse.Namespace) -> int:
    result = assess_gitea_to_forgejo(args.version)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.supported else 2


def _load_report(path: str) -> DeploymentAuditReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "host_label" not in payload and {"name", "host", "service", "resources", "features"} <= payload.keys():
        payload = {
            "host_label": payload["name"],
            "service_model": "systemd"
            if payload["service"].get("install_mode", "").startswith("systemd")
            else payload["service"].get("install_mode", "unknown"),
            "gitea_version": payload["gitea_version"],
            "database_backend": payload["service"]["database"],
            "database_version": payload["postgres_version"],
            "config_path": payload["app_ini_path"],
            "data_root": payload["data_root"],
            "reverse_proxy": payload["service"]["reverse_proxy"],
            "reverse_proxy_port": 80,
            "app_port": 3000,
            "repositories": payload["features"]["repositories"],
            "users": payload["features"]["users"],
            "org_memberships": payload["features"]["org_memberships"],
            "repository_storage_mb": payload["resources"]["repositories_mb"],
            "attachments_storage_mb": payload["resources"]["attachments_mb"],
            "lfs_objects": payload["features"]["lfs_objects"],
            "actions_runs": payload["features"]["action_runs"],
            "action_runners": payload["features"]["action_runners"],
            "packages": payload["features"]["packages"],
            "root_free_gb": payload["resources"]["root_free_gb"],
            "internal_ssh_server": payload["service"].get("ssh_mode") != "host-sshd",
            "lfs_enabled": payload["resources"].get("lfs_mb", 0.0) > 0.0 or payload["features"].get("lfs_objects", 0) > 0,
        }
    return DeploymentAuditReport.from_dict(payload)


def _audit_cmd(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    outcome = evaluate_deployment(report)
    if args.json:
        print(json.dumps({"audit": outcome.to_dict(), "report": report.to_dict()}))
    else:
        print(f"ready: {'yes' if outcome.ready else 'no'}")
        print(f"risk-level: {outcome.risk_level}")
        for finding in outcome.findings:
            print(f"- [{finding.severity}] {finding.code}: {finding.summary}")
    return 0 if outcome.ready else 1


def _gate_cmd(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    assessment = assess_gitea_to_forgejo(report.gitea_version)

    if args.target == "forgejo-current":
        print("allowed: no")
        print("reason: direct jump to current Forgejo is disallowed for this source cohort")
        print("required path: Forgejo 10.x first, then current Forgejo")
        return 1

    if args.target == "forgejo-10":
        allowed = assessment.supported and any(stage.lower().startswith("forgejo-10") for stage in assessment.recommended_stages)
        print(f"allowed: {'yes' if allowed else 'no'}")
        if allowed:
            print("next-stage: forgejo-10.x")
            return 0
        print(f"reason: {assessment.reason}")
        return 1

    print(f"reason: unsupported target {args.target}")
    return 1


def _backup_cmd(args: argparse.Namespace) -> int:
    audit = load_audit(args.audit)
    manifest = build_backup_manifest(audit)
    dump_backup_manifest(args.output, manifest)
    print(args.output)
    return 0


def _smoke_cmd(args: argparse.Namespace) -> int:
    audit = load_audit(args.audit)
    smoke_plan = build_smoke_plan(audit)
    dump_smoke_script(args.output, smoke_plan)
    print(args.output)
    return 0


def _plan_cmd(args: argparse.Namespace) -> int:
    audit = load_audit(args.audit)
    plan = build_migration_plan(audit)
    dump_migration_plan(args.output, plan)
    print(args.output)
    return 0 if plan.stages else 2


def _simulate_cmd(args: argparse.Namespace) -> int:
    audit = load_audit(args.audit)
    report = build_simulation_report(audit)
    dump_json(args.output, report)
    print(args.output)
    return 0


def _collect_live_cmd(args: argparse.Namespace) -> int:
    runner = ShellRunner(ssh_target=args.ssh_target)
    audit = collect_live_audit(runner, app_ini_path=args.app_ini_path, data_root=args.data_root)
    dump_json(args.output, audit.to_dict())
    print(args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gitea-forgejo-migrator")
    sub = parser.add_subparsers(dest="command", required=True)

    compat = sub.add_parser("compatibility", help="Assess source-version compatibility.")
    compat.add_argument("--version", required=True)
    compat.set_defaults(func=_compatibility_cmd)

    audit = sub.add_parser("audit", help="Evaluate a deployment audit report for migration readiness.")
    audit.add_argument("report")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=_audit_cmd)

    gate = sub.add_parser("gate", help="Apply compatibility gates for a target migration stage.")
    gate.add_argument("report")
    gate.add_argument("--target", required=True, choices=["forgejo-10", "forgejo-current"])
    gate.set_defaults(func=_gate_cmd)

    backup = sub.add_parser("backup-manifest", help="Generate a backup manifest from an audit fixture.")
    backup.add_argument("--audit", required=True)
    backup.add_argument("--output", required=True)
    backup.set_defaults(func=_backup_cmd)

    smoke = sub.add_parser("smoke-plan", help="Generate a smoke-check shell script from an audit fixture.")
    smoke.add_argument("--audit", required=True)
    smoke.add_argument("--output", required=True)
    smoke.set_defaults(func=_smoke_cmd)

    plan = sub.add_parser("migration-plan", help="Generate a staged migration plan from an audit fixture.")
    plan.add_argument("--audit", required=True)
    plan.add_argument("--output", required=True)
    plan.set_defaults(func=_plan_cmd)

    simulate = sub.add_parser("simulate", help="Run the local no-touch planning pipeline from an audit fixture.")
    simulate.add_argument("--audit", required=True)
    simulate.add_argument("--output", required=True)
    simulate.set_defaults(func=_simulate_cmd)

    collect = sub.add_parser("collect-live", help="Collect a read-only deployment audit from a local or SSH target.")
    collect.add_argument("--ssh-target", help="SSH target like root@10.200.40.100")
    collect.add_argument("--app-ini-path", default="/etc/gitea/app.ini")
    collect.add_argument("--data-root", default="/var/lib/gitea")
    collect.add_argument("--output", required=True)
    collect.set_defaults(func=_collect_live_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
