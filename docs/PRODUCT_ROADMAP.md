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

## Product Thesis

The product thesis is a **fast in-place migrator** for self-hosted Gitea
installations that want to become Forgejo without changing topology unless the
operator asks for it.

The execution order matters:

1. build a trustworthy server-side admin flow
2. wrap that flow in a GUI without changing the engine
3. use the proven workflow as the basis for proposing native Forgejo migration
   UI support

## Release Tracks

### Track A — Migration Engine

The core engine is responsible for:

- discovery
- compatibility gates
- backup planning and verification
- staged execution
- smoke checks
- rollback journaling

This is the durable product core. Every later interface should reuse it.

### Track B — Operator Experience

The first operator experience is CLI-first and server-side. The second is a GUI
that presents the same decisions, artifacts, and state transitions more
clearly.

### Track C — Upstream Strategy

The long-term strategy is not to maintain a forever-separate migration UI if
Forgejo can absorb the experience cleanly. The standalone product should become
evidence for what native support ought to look like.

## Next Milestones

### Milestone 1 — Read-Only Product

- collect live facts from local or SSH-executed commands
- normalize them into the audit schema
- generate machine-readable reports
- validate supportability before any mutation

Exit criteria:

- audit output is stable enough to act as the contract for later execution
- unsupported cohorts are rejected consistently
- generated reports are useful to both humans and automation

### Milestone 2 — Preflight Guardrails

- backup destination free-space checks
- service liveness checks
- reverse-proxy detection
- Postgres dump verification
- archive integrity verification

Exit criteria:

- the tool can prove rollback artifacts are present before any cutover begins
- preflight failures are actionable and specific
- the tool can emit a migration readiness verdict for operator approval

### Milestone 3 — Staged Executor

- stop/freeze orchestration
- staged binary/package replacement
- migration step journaling
- post-stage smoke checks
- rollback trigger conditions

Exit criteria:

- the engine can perform a full `Gitea 1.22 -> Forgejo 10 -> current Forgejo`
  run on supported cohorts
- every destructive step is journaled
- rollback instructions are generated from run-time facts, not a generic
  template

### Milestone 4 — Admin-Installed Productization

- package the engine for direct server-side installation
- support privileged local execution and admin-SSH execution
- standardize run artifacts and journal locations
- define maintenance-window prompts and operator handoff outputs

Exit criteria:

- an administrator can install and run the migrator without assembling the
  workflow manually
- artifacts are consistent enough to support supportability reviews and GUI
  consumption

### Milestone 5 — Cross-Installation Support

- systemd binary installs
- apt/rpm package installs
- Docker Compose installs
- container image mapping and volume discovery

Exit criteria:

- install-model detection is reliable
- execution logic preserves the deployment shape for each supported cohort
- rollback planning remains explicit across systemd, package, and container
  installs

### Milestone 6 — Guided GUI

- preflight review dashboards
- cutover progress and checkpoint display
- smoke-test status visualization
- rollback-state presentation
- exportable run reports for operators

Exit criteria:

- the GUI is a thin layer over the engine, not a second implementation
- operator decisions and engine decisions stay consistent between CLI and GUI
- support teams can review one artifact model across both interfaces

### Milestone 7 — Edge-Case Library

- Gitea 1.21
- Gitea 1.22
- Gitea 1.23 unsupported guard path
- custom assets
- LFS-heavy instances
- Actions-heavy instances
- package-heavy instances

Exit criteria:

- difficult cohorts are classified early as supported, deferred, or
  expert-only
- smoke coverage expands with each newly supported cohort

### Milestone 8 — Native Forgejo Proposal

- document the admin workflow that proved reliable in the standalone product
- define which parts belong natively in Forgejo admin UX
- propose an upstream-friendly audit bundle and migration-state model
- identify the minimal native UI that improves operator safety without
  overstating support

Exit criteria:

- there is a concrete upstream proposal grounded in field-tested migration runs
- the proposal preserves refusal behavior on unsupported paths
- the standalone product and the upstream direction no longer compete
