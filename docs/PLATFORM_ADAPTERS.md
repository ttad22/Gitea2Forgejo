# Platform Adapters

## Purpose

The migration engine needs a clean boundary between:

- platform-specific deployment handling
- generic migration orchestration

That boundary is the `PlatformAdapter`.

## Current Supported Mutating Adapter

The current real adapter is:

- `SystemdBinaryAdapter`

Supported cohort:

- Linux
- systemd-managed Gitea binary install
- local PostgreSQL
- nginx reverse proxy
- host `sshd`
- Gitea `1.22.x`

## Adapter Responsibilities

Each adapter is responsible for:

1. `supports(audit)`
- state whether the discovered audit matches this adapter cohort

2. `validate(audit)`
- reject unsupported or unsafe layouts within the cohort

3. `detect_layout(runner, audit)`
- resolve runtime paths and deployment identity:
  - binary path
  - service name
  - DB name
  - architecture
  - hostname

4. `backup(...)`
- capture all required rollback artifacts for that cohort

5. `install_release(...)`
- perform the platform-specific cutover for one release stage

6. `rollback(...)`
- restore the cohort to its pre-cutover state if a stage fails

The generic executor owns:

- preflight artifact writing
- compatibility gating
- release resolution
- stage ordering
- journal lifecycle
- outcome emission

## Why This Split Matters

Without adapters, every new install family would force more branching into the
main executor. That becomes brittle quickly.

With adapters:

- systemd-binary stays stable
- Docker Compose can be added without rewriting the executor
- package-managed installs can define their own backup/install/rollback logic
- future native UI can call one engine with the same lifecycle

## Planned Adapter Families

Near-term:

- `SystemdBinaryAdapter`
- `DockerComposeAdapter`
- `PackageManagedAdapter`

Longer-term:

- `PodmanAdapter`
- `MacOSLaunchdAdapter`
- `WindowsServiceAdapter`

## UI Relationship

The future Forgejo admin UI should not implement migration logic directly.

It should:

- detect the cohort
- show the selected adapter
- present the inventory and risk surface
- call the engine lifecycle:
  - `migrate`
  - `validate`
  - `prune`

That keeps the CLI and UI behavior identical.
