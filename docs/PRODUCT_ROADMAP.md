# Product Roadmap

## Current State

The project now has:

- a live audited reference deployment
- an official-compatibility-aware migration runbook
- a Python CLI scaffold for:
  - compatibility gating
  - backup manifest generation
  - migration-plan generation
  - smoke-plan generation
  - fixture-driven simulation

## Next Milestones

### Milestone 1 — Read-Only Product

- collect live facts from local or SSH-executed commands
- normalize them into the audit schema
- generate machine-readable reports
- validate supportability before any mutation

### Milestone 2 — Preflight Guardrails

- backup destination free-space checks
- service liveness checks
- reverse-proxy detection
- Postgres dump verification
- archive integrity verification

### Milestone 3 — Staged Executor

- stop/freeze orchestration
- staged binary/package replacement
- migration step journaling
- post-stage smoke checks
- rollback trigger conditions

### Milestone 4 — Cross-Installation Support

- systemd binary installs
- apt/rpm package installs
- Docker Compose installs
- container image mapping and volume discovery

### Milestone 5 — Edge-Case Library

- Gitea 1.21
- Gitea 1.22
- Gitea 1.23 unsupported guard path
- custom assets
- LFS-heavy instances
- Actions-heavy instances
- package-heavy instances
