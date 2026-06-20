# Forgejo Settings UI Proposal

## Goal

Expose the standalone migration engine inside Forgejo admin settings without
forking the migration logic. The UI should remain a thin shell over the same
`migrate`, `validate`, and `prune` lifecycle that the CLI already uses.

## Placement

The feature should live under:

- `Site Administration`
- `Maintenance`
- `Gitea Migration`

This keeps it:

- admin-only
- operational rather than repository-scoped
- close to other instance-level maintenance actions and backup workflows

Suggested route family:

- `/admin/maintenance/gitea-migration`
- `/admin/maintenance/gitea-migration/preflight`
- `/admin/maintenance/gitea-migration/execute`
- `/admin/maintenance/gitea-migration/validate`
- `/admin/maintenance/gitea-migration/prune`
- `/admin/maintenance/gitea-migration/history/:run_id`

## Page Structure

The page should be a five-step operator workflow.

1. `Eligibility`
- show detected platform adapter
- show source Gitea version
- show supported / blocked cohort
- show refusal reason when unsupported

2. `Inventory`
- show discovered storage/config/runtime surface
- group by:
  - adopted
  - preserved external
  - manual review
- allow export of the inventory bundle

3. `Migration Plan`
- show required stages:
  - Forgejo 10.x
  - current Forgejo
- show maintenance-window estimate
- show backup/rollback coverage

4. `Execution`
- primary action:
  - `Run In-Place Migration`
- secondary action:
  - `Dry Run`
- real-time stage journal:
  - backup
  - forgejo-10
  - forgejo-current
- each stage should expose:
  - started
  - completed
  - failed
  - rollback started/completed

5. `Validation and Cleanup`
- post-cutover `Validate Instance`
- optional `Prune Legacy Gitea State`
- prune stays disabled until validation passes

## Button Model

Buttons should map directly to the CLI lifecycle.

- `Dry Run`
  - calls `migrate --dry-run`
- `Run In-Place Migration`
  - calls `migrate --yes`
- `Validate Instance`
  - future `validate` command
- `Prune Legacy Gitea State`
  - future `prune --yes` command

The UI must not invent alternate migration logic.

## Refusal States

The page should refuse mutation and explain why when:

- no supported platform adapter matches
- source version is not supportable
- backup root is not writable
- required artifacts are missing
- manual-review items exceed the policy threshold

Each refusal should show:

- exact blocking reason
- suggested next action
- whether dry run remains allowed

## Data Model Needed by the UI

The UI can be backed by the existing engine outputs plus two future reports.

Already available:

- `audit.json`
- `backup-manifest.json`
- `migration-plan.json`
- `journal.json`
- `outcome.json`

Should be added next:

- `validation-report.json`
- `prune-report.json`

## Why This Placement Works

This keeps migration:

- instance-scoped
- auditable
- consistent with Forgejo admin mental models
- separable from repository/user/project settings

It also keeps the CLI as the source of truth, which is necessary before any
upstream proposal can be taken seriously.
