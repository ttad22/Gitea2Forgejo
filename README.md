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
- `tooling/`
  - deployment audit scripts
  - backup validation helpers
  - staged migration driver
  - post-cutover smoke checks

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

## Next Build Steps

1. codify the VM audit into a machine-readable report
2. build version-compatibility gating
3. implement backup manifest generation
4. implement preflight and postflight smoke tests
5. implement the staged `1.22 -> Forgejo 10 -> latest Forgejo` orchestration
