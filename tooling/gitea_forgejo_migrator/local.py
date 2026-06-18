from __future__ import annotations

from pathlib import Path


def build_local_runner_script(
    output_dir: str,
    app_ini_path: str = "/etc/gitea/app.ini",
    data_root: str = "/var/lib/gitea",
) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${{1:-{output_dir}}}"
APP_INI="${{GFM_APP_INI:-{app_ini_path}}}"
DATA_ROOT="${{GFM_DATA_ROOT:-{data_root}}}"
TOOLING_ROOT="${{GFM_TOOLING_ROOT:-}}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if python3 - <<'PY' >/dev/null 2>&1
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec("gitea_forgejo_migrator") else 1)
PY
then
  :
elif [ -n "$TOOLING_ROOT" ] && [ -d "$TOOLING_ROOT/gitea_forgejo_migrator" ]; then
  export PYTHONPATH="$TOOLING_ROOT${{PYTHONPATH:+:$PYTHONPATH}}"
else
  echo "gitea_forgejo_migrator is not importable in this Python environment" >&2
  echo "Install the package locally or set GFM_TOOLING_ROOT to the repo's tooling/ directory." >&2
  exit 1
fi

mkdir -p "$OUTDIR"
python3 -m gitea_forgejo_migrator.cli preflight-local \\
  --app-ini-path "$APP_INI" \\
  --data-root "$DATA_ROOT" \\
  --output-dir "$OUTDIR"

echo "preflight-bundle=$OUTDIR"
"""


def write_local_runner(path: str | Path, output_dir: str, app_ini_path: str, data_root: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_local_runner_script(output_dir, app_ini_path, data_root), encoding="utf-8")
    target.chmod(0o755)
    return target
