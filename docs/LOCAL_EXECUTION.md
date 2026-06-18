# Local Execution Path

## Purpose

The preferred early product shape is an administrator-installed, host-local
preflight path. An operator should be able to install the tool on the source
server itself and produce a migration audit without inventing transport glue.

## Current Shape

The current CLI supports:

- `collect-live`
- `emit-local-runner`

`collect-live` can already run locally when no SSH target is supplied.
`emit-local-runner` exists to make the server-local path explicit and
repeatable for operators.

## Example

Emit a wrapper on the source host:

```bash
gitea-forgejo-migrator emit-local-runner \
  --output ./run-preflight.sh \
  --audit-output ./gfm-audit.json
```

Run it on the host:

```bash
./run-preflight.sh
```

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
