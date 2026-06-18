#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


TOOLING_ROOT = Path(__file__).resolve().parent
if str(TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLING_ROOT))

from gitea_forgejo_migrator.preflight import run_local_preflight


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    output_dir = args[0] if args else "live-preflight"
    exit_code, paths, bundle = run_local_preflight(output_dir)
    print(paths["preflight"])
    print(f"ready: {'yes' if bundle['readiness']['ready'] else 'no'}")
    print(f"compatibility-supported: {'yes' if bundle['simulation']['compatibility']['supported'] else 'no'}")
    print(f"risk-level: {bundle['readiness']['risk_level']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
