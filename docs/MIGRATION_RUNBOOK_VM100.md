# Same-VM Migration Runbook — VM100 Gitea to Forgejo

## Decision

For `vm100`, the fastest safe path is a **staged same-VM in-place migration**:

1. `Gitea 1.22.0`
2. `Forgejo 10.x`
3. current stable Forgejo

Do **not** jump directly from `Gitea 1.22.0` to the newest Forgejo build on the
live VM.

## Why This Path

- The instance is still on an officially supported Gitea cohort for staged
  migration.
- The deployment is small enough that a same-VM approach is practical.
- The instance does not actively use the two largest migration pain points:
  Actions and packages.
- Disk headroom is large enough to hold backups and rollback artifacts locally.

## Estimated Time Frame

Assuming no surprises:

- Preflight + backup generation: `20–30 minutes`
- Stop window and package/binary replacement to Forgejo 10.x: `10–15 minutes`
- Validation on Forgejo 10.x: `10–15 minutes`
- Upgrade from Forgejo 10.x to current Forgejo: `10–20 minutes`
- Final validation and smoke tests: `15–20 minutes`

Expected controlled maintenance window:

- **best case:** `45–60 minutes`
- **safer operator estimate:** `60–90 minutes`

## Preflight Checklist

1. Confirm current backups succeed.
2. Snapshot the VM at the hypervisor layer.
3. Create an application backup set:
   - PostgreSQL dump
   - `/etc/gitea/app.ini`
   - `/var/lib/gitea/custom`
   - `/var/lib/gitea/data`
   - `/var/lib/gitea/lfs`
   - `/var/lib/gitea/log`
4. Record current service status:
   - `systemctl status gitea nginx postgresql`
5. Record current app version and database version.
6. Record current disk usage before the upgrade.

## Same-VM Execution Sequence

### Phase 1 — Freeze and Backup

1. Announce maintenance window.
2. Stop incoming writes if you want a cleaner final state.
3. Stop Gitea cleanly.
4. Create the final DB dump.
5. Archive Gitea config and work directories.
6. Create the VM snapshot if not already taken immediately prior.

### Phase 2 — Stage to Forgejo 10.x

1. Install or replace the Gitea binary/package with the Forgejo `10.x` release
   appropriate for the host OS and installation model.
2. Preserve:
   - `/etc/gitea/app.ini`
   - `/var/lib/gitea`
   - service paths
3. If environment variables are used later, mirror both:
   - `GITEA_*`
   - `FORGEJO_*`
4. Start Forgejo 10.x.
5. Let its schema migrations complete.

### Phase 3 — Validate Forgejo 10.x

Run smoke checks:

- UI login
- repo browse
- HTTPS clone
- SSH clone
- create branch / push test
- issue view
- PR view
- webhook list
- LFS endpoint sanity

If this fails materially, rollback immediately to Gitea from the preserved
binary/package and data snapshot.

### Phase 4 — Upgrade to Current Forgejo

1. Replace Forgejo 10.x with the current target Forgejo release.
2. Start the service.
3. Allow the newer migrations to complete.
4. Repeat the smoke checks.

## Post-Cutover Validation

1. `systemctl is-active forgejo nginx postgresql`
2. web health endpoint
3. UI login as admin and non-admin
4. HTTP clone of a private repo
5. SSH clone of a private repo
6. push test to a disposable repo
7. attachments load
8. repository archives download
9. LFS endpoint sanity, even though currently unused
10. webhooks can still be delivered

## Rollback Plan

Rollback is straightforward if performed before any incompatible later-stage
manual data rewriting:

1. stop Forgejo
2. restore the prior Gitea binary/package
3. restore:
   - PostgreSQL dump
   - `/etc/gitea/app.ini`
   - `/var/lib/gitea`
4. start Gitea
5. verify UI, clone, and push

If rollback is required after the second-stage Forgejo upgrade, restore from the
captured backup set rather than trying to downgrade database state in place.

## Open-Source Tooling Implications

The planned `GiteaForgejoMigrator` tool should implement:

1. deployment discovery
2. compatibility gating
3. backup manifest generation
4. service freeze orchestration
5. staged version target enforcement
6. postflight smoke tests
7. rollback instructions generation

It should explicitly refuse unsupported direct upgrade paths unless the operator
opts into an expert/manual mode.
