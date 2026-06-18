#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:-./gfm-preflight}"
APP_INI="${GFM_APP_INI:-/etc/gitea/app.ini}"
DATA_ROOT="${GFM_DATA_ROOT:-/var/lib/gitea}"
TOOLING_ROOT="${GFM_TOOLING_ROOT:-}"

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
  export PYTHONPATH="$TOOLING_ROOT${PYTHONPATH:+:$PYTHONPATH}"
else
  echo "gitea_forgejo_migrator is not importable in this Python environment" >&2
  echo "Install the package locally or set GFM_TOOLING_ROOT to the repo's tooling/ directory." >&2
  exit 1
fi

mkdir -p "$OUTDIR"
python3 -m gitea_forgejo_migrator.cli preflight-local \
  --app-ini-path "$APP_INI" \
  --data-root "$DATA_ROOT" \
  --output-dir "$OUTDIR"

echo "preflight-bundle=$OUTDIR"
