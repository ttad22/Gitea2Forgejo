# Local Execution Path

## Purpose

The preferred early product shape is an administrator-installed, host-local
preflight path. An operator should be able to install the tool on the source
server itself and produce a migration audit without inventing transport glue.

## Current Shape

The current CLI supports:

- `collect-live`
- `preflight-local`
- `emit-local-runner`

`collect-live` can already run locally when no SSH target is supplied.
`emit-local-runner` exists to make the server-local path explicit and
repeatable for operators.

## Host Prerequisites

The host-local path is intentionally read-only, but it is not magic. The
operator still needs:

- `python3 >= 3.10`
- the `gitea-forgejo-migrator` package installed, or a checkout with
  `GFM_TOOLING_ROOT` pointing at its `tooling/` directory
- normal inspection binaries already present on the host:
  `sed`, `awk`, `cut`, `df`, `du`, `grep`, `head`, `curl`, `ss`, `systemctl`
- access to whichever application binaries and data paths the source instance
  actually uses
- permission to run read-only metadata queries against the configured database

The default discovery paths are:

- app config: `/etc/gitea/app.ini`
- data root: `/var/lib/gitea`

Override them for non-standard installs.

## Example

Emit a wrapper on the source host:

```bash
gitea-forgejo-migrator emit-local-runner \
  --output ./run-preflight.sh \
  --output-dir ./gfm-preflight
```

Run it on the host:

```bash
./run-preflight.sh
```

This creates:

- `./gfm-preflight/audit.json`
- `./gfm-preflight/readiness.json`
- `./gfm-preflight/backup-manifest.json`
- `./gfm-preflight/migration-plan.json`
- `./gfm-preflight/smoke.sh`

Override non-default paths if needed:

```bash
GFM_APP_INI=/custom/app.ini \
GFM_DATA_ROOT=/srv/gitea \
./run-preflight.sh /tmp/custom-audit.json
```

## Why This Matters

This keeps the product generic:

- no Proxmox assumptions
- no hardcoded jump-host logic
- no dependency on a central orchestrator

The host-local path should remain the reference path even after a GUI exists.
