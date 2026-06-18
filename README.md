# GiteaForgejoMigrator

Open-source migration tooling and runbooks for moving self-hosted Gitea
instances to Forgejo with an emphasis on safe, low-downtime, operator-friendly
upgrades.

## Purpose

Most migration advice assumes either:

- a greenfield Forgejo deployment, or
- a repo-by-repo import flow

That is not enough for operators who need to preserve a live instance in place,
keep SSH/HTTP clone behavior stable, retain issues and pull requests, and avoid
blind database surgery.

This project focuses on:

- deployment auditing
- compatibility gating
- backup validation
- staged upgrade orchestration
- rollback preparation
- post-cutover verification

## Operator Workflows

The tool is designed around two execution modes:

1. **Server-local admin run**
   - install the package on the source host
   - emit a local wrapper
   - collect and evaluate the deployment on-box
   - use the generated audit as the contract for backup, planning, and smoke
     artifacts
2. **Trusted admin-SSH run**
   - run the collector from a management host with direct administrative SSH
   - preserve the same audit schema and downstream planning flow

The product should keep both paths first-class. The transport should be
replaceable; the migration model should not be.

## Current TTT Reference Deployment

The initial design target is the live `git-ops` VM (`vm100`) in the TTT
environment.

Observed deployment characteristics from the audit on `2026-06-18`:

- VM name: `git-ops`
- Address: `10.200.40.100`
- Service model: `systemd`, not Docker
- Gitea version: `1.22.0`
- Database: `PostgreSQL 14`
- App config: `/etc/gitea/app.ini`
- Data root: `/var/lib/gitea`
- Reverse proxy: `nginx` on `:80`
- Gitea listener: `:3000`
- Repositories: `36`
- Users: `5`
- Org memberships: `2`
- Repository storage: about `795 MB`
- Attachments: about `80 MB`
- LFS objects: `0`
- Actions runs: `0`
- Packages: `0`
- Root filesystem free space: about `188 GB`

## Migration Constraint That Drives The Design

The live TTT instance is on `Gitea 1.22.0`, which is significant because
current official Forgejo guidance still supports an upgrade path from `Gitea
1.22.x`, but not a transparent direct path from `Gitea 1.23+`.

That means the tool should treat `1.22.x` as a first-class migration cohort and
explicitly gate anything newer.

## Design Principles

1. Audit before mutation.
2. Refuse unsupported direct upgrade paths.
3. Always create both application-level and VM-level rollback points.
4. Preserve existing paths, secrets, and SSH behavior unless the operator asks
   to change them.
5. Separate compatibility checks from execution logic.
6. Make dry-run the default.

## Planned Components

- `docs/`
  - operator runbooks
  - compatibility matrix
  - rollback procedures
  - product direction and future-work proposals
- `tooling/`
  - deployment audit scripts
  - backup validation helpers
  - staged migration driver
  - post-cutover smoke checks

## CLI Surface

Current commands:

- `compatibility`
- `audit`
- `gate`
- `backup-manifest`
- `migration-plan`
- `smoke-plan`
- `simulate`
- `collect-live`
- `emit-local-runner`

The CLI should remain dry-run centric until the executor exists.

## Scope Boundaries

This project is not trying to:

- rewrite Gitea/Forgejo database schemas generically for all unsupported
  versions
- replace official upgrade documentation
- hide operator risk where upstream compatibility is explicitly absent

It is trying to:

- make supported paths safer
- make unsupported paths easier to classify early
- reduce operator error during in-place or same-host migrations

## Product Direction

The near-term product target is not a hosted migration service and not a
repo-by-repo importer. It is a **fast in-place migrator** that an operator
installs on the source server or runs with direct administrative access to the
source server.

That implies a product shape with three phases:

1. **Admin-installed server-side flow**
   - packaged for direct operator use on the live host
   - runs audits, backups, compatibility gates, staged execution, and smoke
     checks locally or over trusted admin SSH
   - optimized for the smallest realistic maintenance window and the simplest
     rollback story
2. **Later GUI release**
   - wraps the same migration engine in a guided operator interface
   - exposes preflight results, maintenance steps, live logs, and rollback
     checkpoints without changing the execution model
   - aimed at MSP and infra teams that need repeatability across many small
     self-hosted instances
3. **Long-term native Forgejo support**
   - use evidence from the standalone migrator to propose native migration UX
     inside Forgejo itself
   - focus on turning a validated admin workflow into upstream-supported UI
     affordances rather than carrying a permanent forked experience

The core rule across all three phases is the same: preserve the existing
instance shape whenever possible. Keep paths, database backend, SSH behavior,
reverse proxy behavior, and clone URLs stable unless the operator explicitly
chooses to change them.

## Product Boundaries

The intended product should:

- prioritize in-place and same-host migrations first
- treat server-side installability as a feature, not a temporary workaround
- keep execution auditable through generated plans, manifests, journals, and
  smoke reports
- prefer refusal and escalation over speculative mutation when upstream support
  is unclear

The intended product should not:

- depend on a cloud control plane for routine migration execution
- require an operator to manually stitch together multiple ad hoc scripts during
  a cutover
- assume that every target instance wants a new Forgejo host or a fresh URL

## Future Work

See [docs/PRODUCT_ROADMAP.md](/home/svc-opsd/TTT-Research/projects/GiteaForgejoMigrator/docs/PRODUCT_ROADMAP.md)
for milestone sequencing and
[docs/FUTURE_PRODUCT_DIRECTION.md](/home/svc-opsd/TTT-Research/projects/GiteaForgejoMigrator/docs/FUTURE_PRODUCT_DIRECTION.md)
for the detailed proposal covering:

- the admin-installed server-side flow
- the later GUI product layer
- the long-term path toward native Forgejo UI migration support

## Next Build Steps

1. build the executor journal and mutation-stage interfaces
2. add broader edge-case fixture coverage and compatibility matrices
3. add install-model aware preflight checks for systemd, package, and Docker
4. test server-local installation and live collection on a reference host
5. implement the staged `1.22 -> Forgejo 10 -> latest Forgejo` orchestration
