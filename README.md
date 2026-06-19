# GiteaForgejoMigrator

![Gitea → Forgejo](assets/banner.svg)

Operator-first preflight, gating, and staging plan for **in-place
Gitea → Forgejo migrations**.

> Once you've migrated, you're done. There is no plan for what comes
> after, because there is no "after". This tool exists so a sysadmin
> can ship a Gitea → Forgejo cutover in a single maintenance window,
> validate it, and move on.

---

## Why this tool exists

Most public migration advice assumes either a *greenfield* Forgejo
deployment or a *repo-by-repo* import flow. Neither fits operators who
need to:

- preserve a live Gitea instance in place
- keep SSH and HTTP clone URLs stable
- keep issues, pull requests, attachments, and LFS intact
- avoid blind database surgery
- finish inside a short maintenance window

`GiteaForgejoMigrator` starts with preflight + planning and now ships a
first execution engine for the supported cohort. It produces and
consumes the artifacts needed to do that cutover safely:

| Artifact                   | From                              | Used by              |
|----------------------------|-----------------------------------|----------------------|
| deployment audit report    | `collect-live` / fixture JSON     | you, your reviewer   |
| readiness evaluation       | `audit`                           | gate / proceed check |
| compatibility gate         | `gate`                            | CI / pre-cutover     |
| backup manifest            | `backup-manifest`                 | `freeze-and-backup` step |
| staged migration plan      | `migration-plan`                  | the runbook          |
| smoke-check shell script   | `smoke-plan`                      | post-cutover validation |
| no-touch dry-run report    | `simulate`                        | you, your reviewer   |
| staged in-place migration  | `migrate`                         | the maintenance window |

The mutating path is intentionally narrow. The tool only executes a real
cutover for the supported cohort described below.

## Scope

This tool is meant to be portable across common self-hosted Gitea
deployments, but it does **not** claim universal compatibility with every
possible environment. The current alpha has:

- one **supported mutating executor cohort**:
  - `systemd-binary`
  - local `PostgreSQL`
  - `nginx`
  - `host-sshd`
  - `Gitea 1.22.x`
- broader **read-only modeled cohorts** used for gating and fixture coverage:
  - Docker Compose install
  - SQLite backend
  - Actions-enabled instance
  - LFS-heavy instance
  - blocked `1.23+ -> current Forgejo` direct-upgrade cohort

Anything outside those cohorts should be treated as unsupported until a
fixture and validation path are added for it.

## Installation

The tool is a pure-Python package with **no runtime dependencies**.
Python ≥ 3.10 is required.

### Option A — install from GitHub (default)

```bash
pip install "git+https://github.com/ttad22/Gitea2Forgejo.git@main"
```

After this, the `gitea-forgejo-migrator` command is on your `$PATH`.

### Option B — install from a local clone

```bash
git clone https://github.com/ttad22/Gitea2Forgejo.git
cd Gitea2Forgejo
pip install .
```

## Quick Start

```bash
# 1. Collect a live audit (server-local or with --ssh-target)
gitea-forgejo-migrator collect-live \
    --ssh-target admin@git.example.internal \
    --output ./my-audit.json

# 2. Read-only evaluation against the audit
gitea-forgejo-migrator audit ./my-audit.json

# 3. Gate against the next target version
gitea-forgejo-migrator gate ./my-audit.json --target forgejo-10
gitea-forgejo-migrator gate ./my-audit.json --target forgejo-current

# 4. Generate the artifacts the runbook needs
gitea-forgejo-migrator backup-manifest --audit   ./my-audit.json --output ./backup.json
gitea-forgejo-migrator migration-plan  --audit   ./my-audit.json --output ./plan.json
gitea-forgejo-migrator smoke-plan      --audit   ./my-audit.json --output ./smoke.sh

# 5. Run the no-touch dry-run pipeline
gitea-forgejo-migrator simulate --audit ./my-audit.json --output ./dryrun.json
```

The supported path at the moment is:

```
Gitea 1.22.x  →  Forgejo 10.x  →  current Forgejo
```

The `gate` command will refuse to give you a direct path to current
Forgejo from Gitea 1.23+. This refusal is intentional and matches
upstream Forgejo guidance.

## Admin-Run Path

The intended operator flow is:

1. install the package on the source host
2. run `emit-local-runner`
3. execute the generated wrapper locally
4. review the generated audit, gate, backup, plan, and smoke artifacts

Example:

```bash
pip install "git+https://github.com/ttad22/Gitea2Forgejo.git@main"
gitea-forgejo-migrator emit-local-runner \
    --output ./run-preflight.sh \
    --output-dir ./gfm-preflight
./run-preflight.sh
```

## One-Command Supported Migration

For the modeled cohort, the admin can run:

```bash
sudo env PATH="$HOME/.local/bin:$PATH" \
  gitea-forgejo-migrator migrate --yes
```

That command will:

- auto-detect the supported install shape
- capture backup artifacts into a timestamped run directory
- preserve the live PostgreSQL data, repository root, config, custom data,
  attachments, SSH authorized-keys material, and LFS content for rollback
- harvest additional existing absolute paths declared in `app.ini` and preserve
  them as config-bound artifacts when they exist on disk
- resolve the latest Forgejo `10.x` release and the latest current release
- stage `Gitea 1.22.x -> Forgejo 10.x -> current Forgejo`
- run critical smoke checks after each stage
- attempt rollback if a post-backup stage fails

The admin still has to:

- install the package
- run the mutating path as `root`
- point it at non-standard `app.ini` or data-root paths if needed
- ensure inspection and backup binaries are available
- review the retained artifacts under the migration run directory

## Command Surface (alpha)

| Command             | Purpose                                                           |
|---------------------|-------------------------------------------------------------------|
| `compatibility`     | Assess a single Gitea source version                              |
| `audit`             | Evaluate a deployment audit fixture for readiness + risk          |
| `gate`              | Compatibility gate for the next migration target                  |
| `backup-manifest`   | Produce the freeze-and-backup checklist                          |
| `migration-plan`    | Produce a staged migration plan + rollback summary                |
| `smoke-plan`        | Produce a post-cutover smoke-check shell script                  |
| `simulate`          | Run the local no-touch pipeline against a fixture                 |
| `collect-live`      | Read-only audit collected via SSH or on-host shell                |
| `emit-local-runner` | Emit a server-local wrapper the admin runs by hand                |
| `preflight-local`   | Run the audit + plan + smoke pipeline locally on the source host  |
| `migrate`           | Execute the supported staged in-place migration with rollback     |

## Compatibility Matrix (alpha)

| Source Gitea  | Allowed next target  | Notes                                    |
|---------------|----------------------|------------------------------------------|
| `1.21.x`      | unsupported in alpha | Needs a fixture + rule (PRs welcome)     |
| `1.22.x`      | `forgejo-10`         | Recommended staging cohort               |
| `1.22.x`      | `forgejo-current`    | **Refused** by `gate`; stage first       |
| `1.23+`       | `forgejo-10`         | Blocked — upstream Gitea 1.23 cutover    |
| `1.23+`       | `forgejo-current`    | Blocked — see `gitea-123-blocked` fixture|

The matrix lives in code at
`tooling/gitea_forgejo_migrator/compatibility.py`. Edge cases
(`docker-audit.json`, `sqlite-audit.json`, `actions-audit.json`,
`lfs-heavy-audit.json`, `gitea-123-blocked-audit.json`) live under
`fixtures/`.

## Design Principles

1. **Audit before mutation.** We never recommend a cutover without
   reading the source instance first.
2. **Refuse unsupported direct paths.** Hard refusals are a feature.
3. **Always produce both app-level and VM-level rollback points.**
4. **Preserve existing paths, secrets, and SSH behavior by default.**
5. **Separate compatibility checks from execution logic.**
6. **Make dry-run the default.** Anything that *would* mutate is a
   separate, opt-in subcommand.
7. **No transport assumptions in product core.** The collector uses a
   generic shell; transport choices belong to the operator.

The CLI is **terminal-only** in alpha. There is no GUI, no daemon, no
agent installed on the source host. The host-local runner script
(`emit-local-runner`) is still generated on demand, not installed as a
service.

## Repository Layout

```
.
├── README.md              ← this file
├── CHANGELOG.md
├── CONTRIBUTING.md
├── RELEASING.md
├── LICENSE
├── pyproject.toml
├── setup.cfg
├── MANIFEST.in
├── .gitignore
├── assets/                ← logo + icon + banner + social card (SVG)
├── docs/                  ← runbooks and product direction
├── fixtures/              ← edge-case audit JSONs
├── scripts/               ← read-only transport helpers
├── tests/                 ← pytest suite
└── tooling/gitea_forgejo_migrator/   ← source package
```

## Documentation

- [`docs/LOCAL_EXECUTION.md`](docs/LOCAL_EXECUTION.md)
- [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md)
- [`docs/FUTURE_PRODUCT_DIRECTION.md`](docs/FUTURE_PRODUCT_DIRECTION.md)

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

`pytest` covers audit, compatibility, backup planning, discovery,
pipeline, smoke harness, journal, local runner, release resolution,
execution, CLI surface, and every fixture in the matrix.

## License

BSD 3-Clause — see [LICENSE](LICENSE).

## Acknowledgements

The **pre-flight contribution questions** in `CONTRIBUTING.md` are
adapted from
[sohaibt/product-mode](https://github.com/sohaibt/product-mode) (MIT,
Sohaib Tanveer), used under the project's purpose of letting small
contributions carry clear rationale.
