from __future__ import annotations

import argparse
import json

from .backup import build_backup_manifest
from .compatibility import assess_gitea_to_forgejo
from .discovery import collect_live_audit
from .io import dump_backup_manifest, dump_json, dump_migration_plan, dump_smoke_script, load_audit
from .planning import build_migration_plan
from .shell import ShellRunner
from .simulate import build_simulation_report
from .smoke import build_smoke_plan


def _compatibility_cmd(args: argparse.Namespace) -> int:
    result = assess_gitea_to_forgejo(args.version)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.supported else 2


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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
