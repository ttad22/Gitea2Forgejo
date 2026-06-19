# Contributing to GiteaForgejoMigrator

Thanks for your interest in this tool. It is intentionally small. Most
contributions are one of three kinds:

1. **A new edge-case fixture** — a JSON audit under `fixtures/` that
   represents a Gitea deployment the matrix does not yet cover.
2. **A new compatibility rule** — extending the gate so another source
   cohort is recognized.
3. **A bug fix** in any of the modules under `tooling/gitea_forgejo_migrator/`.

## Pre-Flight Questions (read these before opening a PR)

This project borrows the pre-flight checklist idea from
[product-mode](https://github.com/sohaibt/product-mode). Before writing
non-trivial code, answer these in the PR description:

1. **Problem.** What operator question does this change answer?
2. **Why now.** Why is this contribution timely? Which real instance
   does it unblock?
3. **Scope.** What is the smallest realistic change that solves it?
   What is intentionally out of scope?
4. **Success metric.** How will a reviewer know the change worked?
   (e.g., new fixture passes `pytest`, gate returns the expected code,
   a runbook command produces the expected output.)
5. **Reversibility.** If this turns out wrong, what is the rollback
   plan? (For pure code: revert; for behavior change: feature flag.)

If a question is genuinely not applicable (typo fix, doc cleanup), say
so — that is a legitimate answer in this project too.

## Local Setup

```bash
git clone https://github.com/joshrfr/gitea-forgejo-migrator.git
cd gitea-forgejo-migrator
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

`pip install -e .` registers the `gitea-forgejo-migrator` console
script so you can iterate without reinstalling.

## Test Layout

- `tests/test_audit.py` — readiness evaluation logic.
- `tests/test_compatibility.py` — version gate rules.
- `tests/test_pipeline.py` — end-to-end audit → plan → smoke pipeline.
- `tests/test_backup_planner.py` — backup manifest generation.
- `tests/test_smoke_harness.py` — post-cutover smoke simulation.
- `tests/test_journal.py` — append-only journal for executor runs.
- `tests/test_local.py` — server-local runner.
- `tests/test_fixture_matrix.py` — parametrized assertions over every
  `fixtures/*.json`.
- `tests/test_cli.py` — argparse surface smoke checks.
- `tests/test_discovery.py` — read-only live audit shape.

## Adding a New Edge-Case Fixture

1. Drop a JSON file under `fixtures/` named `<scenario>-audit.json`.
2. The shape must match `fixtures/vm100-audit.json`. Top-level keys:
   `name`, `host`, `gitea_version`, `postgres_version`, `app_ini_path`,
   `data_root`, `service`, `resources`, `features`, `notes`.
3. Add at least one assertion in `tests/test_fixture_matrix.py` —
   the matrix is the contract.
4. Run `pytest -q`. The new fixture should be picked up automatically.

## Commit Messages

Use Conventional-Commits-flavored messages:

```
feat(audit): add medium-risk path for sqlite-with-lfs-objects
fix(cli): make collect-live return non-zero on remote errors
docs(runbook): clarify forgejo-10 stage ordering
```

## Code Style

- Python ≥ 3.10, type hints on all public functions.
- Keep modules under `tooling/gitea_forgejo_migrator/` importable as a
  standard package; do not rely on the test-time `conftest.py` path hack
  for shipped code.
- No external runtime dependencies unless added to `pyproject.toml`.

## Reporting a Bug

Open a GitHub issue with:

- The exact CLI command and `--version` outputs that reproduce it.
- The audit JSON (or its `name` + `gitea_version` if redactable).
- The expected audit/gate outcome vs the actual one.
