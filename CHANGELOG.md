# Changelog

All notable changes to **GiteaForgejoMigrator** are documented in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Live `collect-live` enrichment via opt-in Forgejo API admin token.
- Optional npm-published thin `npx` wrapper around the Python CLI.
- Additional edge-case fixtures (Docker Compose install, SQLite-with-LFS, actions-with-real-runners, gitea 1.21 pre-staging cohort).

## [0.1.0-alpha.1] - 2026-06-19

### Added
- Initial alpha of the operator preflight and staging plan tool.
- CLI surface: `compatibility`, `audit`, `gate`, `backup-manifest`,
  `migration-plan`, `smoke-plan`, `simulate`, `collect-live`,
  `emit-local-runner`, `preflight-local`.
- Edge-case fixture matrix covering Docker install, SQLite backend,
  Actions-enabled instance, LFS-heavy instance, and Gitea 1.23+ blocked cohort.
- Local runner wrapper script generator (`emit-local-runner`) so an
  admin can run the preflight directly on the source server without
  baking a transport into the product core.
- Test suite covering audit, backup planning, compatibility, discovery,
  pipeline, smoke harness, journal, local runner, CLI, and the fixture
  matrix.
- Documentation set: this README, `docs/MIGRATION_RUNBOOK_VM100.md`,
  `docs/VM100_AUDIT_2026-06-18.md`, `docs/LOCAL_EXECUTION.md`,
  `docs/PRODUCT_ROADMAP.md`, `docs/FUTURE_PRODUCT_DIRECTION.md`.

### Notes (intentional design constraints, surfaced here for visibility)
- The collector is **read-only**: the tool produces audits, manifests,
  plans, and smoke scripts but never mutates the source instance.
- The product core is transport-agnostic: no Proxmox assumptions, no
  cloud control plane, no fixed jump-host logic — `preflight-local` and
  the SSH runner are the only transports.
- The CLI is **terminal-only** in alpha; no GUI, no daemon, no
  long-running agent on the source host. The host-local runner script
  (`emit-local-runner`) is generated on demand, not installed as a
  service.

[0.1.0-alpha.1]: https://github.com/joshrfr/gitea-forgejo-migrator/releases/tag/v0.1.0-alpha.1
