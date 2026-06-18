from __future__ import annotations

import argparse
import json
from pathlib import Path

from .harness import SimulationHarness
from .planner import PlanStage, build_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and simulate migration smoke checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Render a smoke-check plan.")
    plan_parser.add_argument("--stage", choices=[stage.value for stage in PlanStage], required=True)
    plan_parser.add_argument("--required-only", action="store_true", help="Exclude optional checks.")

    run_parser = subparsers.add_parser("run", help="Execute a plan against a local simulation fixture.")
    run_parser.add_argument("--stage", choices=[stage.value for stage in PlanStage], required=True)
    run_parser.add_argument("--fixture", required=True, type=Path)
    run_parser.add_argument("--required-only", action="store_true", help="Exclude optional checks.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    include_optional = not args.required_only
    plan = build_plan(args.stage, include_optional=include_optional)

    if args.command == "plan":
        print(json.dumps(plan.to_dict(), indent=2))
        return 0

    harness = SimulationHarness.from_path(args.fixture)
    report = harness.run(plan)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
