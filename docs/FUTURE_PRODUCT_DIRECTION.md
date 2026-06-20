# Future Product Direction

## Thesis

The product should become the fastest safe path for an administrator to migrate
an existing self-hosted Gitea instance to Forgejo **in place**. It should not
start as a hosted orchestrator or a repo-by-repo importer.

The initial value is operational:

- classify whether a source cohort is supportable
- prove rollback assets exist
- generate a staged plan
- execute and validate the migration with the smallest realistic maintenance
  window

## Phase 1: Admin-Installed Server-Side Flow

The first real release should assume an operator can install a package or drop
in a release artifact on the source host itself.

That server-side release should provide:

- local deployment audit
- compatibility gate
- backup manifest and verification
- generated local runner / wrapper path
- staged execution journal
- smoke checks before and after each migration stage
- rollback checkpoints tied to run-time state

It should not require:

- a central control plane
- a SaaS dependency
- a second host by default

## Phase 2: Guided GUI

The later GUI should be a thin operator shell over the same engine.

It should add:

- preflight review
- maintenance-window checklist presentation
- live stage progress
- smoke-check visualization
- rollback-state visibility
- exportable reports for support and change management

It should not introduce:

- a second execution engine
- GUI-only migration logic
- opaque hidden decisions that differ from CLI behavior

## Phase 3: Native Forgejo Proposal

Once the standalone tool is field-tested, the next step is to propose a native
Forgejo admin migration experience.

That proposal should be grounded in:

- real migration run journals
- real unsupported-cohort refusal cases
- the minimum audit bundle needed for operator safety
- the minimum UI needed to make supportable paths easier

The likely upstreamable pieces are:

- audit bundle schema
- supportability gate presentation
- backup/rollback checklist model
- staged migration status model

The likely non-upstreamable pieces are:

- bespoke transport adapters
- environment-specific wrapper scripts
- private infrastructure orchestration

See [FORGEJO_SETTINGS_UI_PROPOSAL.md](./FORGEJO_SETTINGS_UI_PROPOSAL.md) for
the proposed admin IA, page structure, refusal states, and lifecycle mapping.

## Long-Term Position

If the standalone migrator works well, it should become:

- the execution engine for supported same-host migrations
- the reference workflow for support teams
- the evidence base for a native Forgejo migration UI

The project should remain strict about refusal behavior. Unsupported cohorts
must still fail fast rather than being nudged into dangerous “best effort”
mutation.
