# Changelog

All notable changes to **GiteaForgejoMigrator** are documented in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Live `collect-live` enrichment via opt-in Forgejo API admin token.
- Optional npm-published thin `npx` wrapper around the Python CLI.
- Additional edge-case fixtures (Docker Compose install, SQLite-with-LFS, actions-with-real-runners, gitea 1.21 pre-staging cohort).
- Additional execution adapters beyond the alpha cohort (`docker-compose`, `sqlite`, `actions-heavy`, `lfs-heavy`).

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
- Supported execution engine for the narrow alpha cohort:
  `systemd-binary + local PostgreSQL + nginx + host sshd + Gitea 1.22.x`.
- Release resolution through the Forgejo Codeberg API for latest `10.x`
  and latest current binary assets.
- Automatic rollback attempt after a post-backup failure in the
  supported migration path.

### Notes (intentional design constraints, surfaced here for visibility)
- The collector remains **read-only**, but the product now also ships a
  separate mutating `migrate` command for the supported cohort only.
- The product core is transport-agnostic: no Proxmox assumptions, no
  cloud control plane, no fixed jump-host logic — `preflight-local` and
  the SSH runner are the only transports.
- The CLI is **terminal-only** in alpha; no GUI, no daemon, no
  long-running agent on the source host. The host-local runner script
  (`emit-local-runner`) is generated on demand, not installed as a
  service.

[0.1.0-alpha.1]: https://github.com/ttad22/Gitea2Forgejo/releases/tag/v0.1.0-alpha.1
