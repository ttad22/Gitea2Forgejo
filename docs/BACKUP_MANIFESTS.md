# Backup Manifest Planning

The backup slice under `tooling/backup` turns an audited Gitea deployment into
a deterministic manifest and a stage-aware rollback plan.

## What the manifest covers

- PostgreSQL logical dump
- `/etc/gitea/app.ini`
- `/var/lib/gitea/custom`
- `/var/lib/gitea/data`
- `/var/lib/gitea/lfs`
- `/var/lib/gitea/log`

Each artifact records:

- a stable artifact id
- the source path
- the capture method
- an estimated size
- whether it is required for rollback
- a lightweight integrity check to run after capture

## Planning assumptions

1. The source deployment is a same-host `systemd` installation like `vm100`.
2. A hypervisor snapshot is still required immediately before cutover.
3. The application-level backup set is the rollback source of truth once later
   Forgejo migrations have been attempted.
4. Recommended free space is `2x` the estimated backup footprint so the host can
   hold both backup artifacts and a rollback working margin.

## Rollback stages

- `pre-stage`
  - before the first staged Forgejo migration commits schema changes
  - prefer the VM snapshot; keep artifacts as a secondary checkpoint
- `forgejo-10`
  - rollback remains a normal package/binary restore plus full data restore
- `current-forgejo`
  - downgrade in place is not trusted
  - treat rollback as a full restore from the captured manifest and snapshot

## Test entry point

Run:

```bash
pytest tests/test_backup_planner.py
```
