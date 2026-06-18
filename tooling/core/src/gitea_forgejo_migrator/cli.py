from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import evaluate_deployment
from .compatibility import evaluate_compatibility
from .models import DeploymentAuditReport


def _load_report(path: str) -> DeploymentAuditReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Audit input must be a JSON object")
    return DeploymentAuditReport.from_dict(payload)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gfm-core")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Evaluate deployment readiness from an audit JSON report.")
    audit_parser.add_argument("report", help="Path to a deployment audit JSON file.")
    audit_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    gate_parser = subparsers.add_parser("gate", help="Apply compatibility gating for a target migration stage.")
    gate_parser.add_argument("report", help="Path to a deployment audit JSON file.")
    gate_parser.add_argument("--target", required=True, choices=["forgejo-10", "forgejo-current"])
    gate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def _print_audit(report: DeploymentAuditReport, *, as_json: bool) -> int:
    outcome = evaluate_deployment(report)
    payload = {
        "report": report.to_dict(),
        "audit": outcome.to_dict(),
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"host: {report.host_label}")
        print(f"ready: {'yes' if outcome.ready else 'no'}")
        print(f"risk: {outcome.risk_level}")
        if outcome.findings:
            for finding in outcome.findings:
                print(f"{finding.severity}: {finding.code}: {finding.message}")
    return 0 if outcome.ready else 1


def _print_gate(report: DeploymentAuditReport, *, target: str, as_json: bool) -> int:
    audit_outcome = evaluate_deployment(report)
    decision = evaluate_compatibility(report, target=target, audit_outcome=audit_outcome)
    payload = {
        "report": report.to_dict(),
        "audit": audit_outcome.to_dict(),
        "compatibility": decision.to_dict(),
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"host: {report.host_label}")
        print(f"target: {decision.target}")
        print(f"allowed: {'yes' if decision.allowed else 'no'}")
        print("path: " + " -> ".join(decision.recommended_path))
        for message in decision.blocking_reasons:
            print(f"blocker: {message}")
        for message in decision.warnings:
            print(f"warning: {message}")
    return 0 if decision.allowed else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    report = _load_report(args.report)
    if args.command == "audit":
        return _print_audit(report, as_json=args.json)
    return _print_gate(report, target=args.target, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
