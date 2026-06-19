# Release Process

This is the **operating** release procedure for cutting an alpha or
stable release. The CLI and Python package stay aligned in version.

## Versioning

The project follows [Semantic Versioning 2.0.0](https://semver.org/) but
**for pre-1.0 releases minor versions are reserved for behavior
changes**. Concretely:

- **0.x.y-alpha.z** — alpha of an upcoming minor. CLI may shift.
- **0.x.y** — minor release of the 0.x line. CLI stable within the line.
- **1.0.0** — first stable. CLI surface stable across the 1.x line.

### When to bump

| Change kind                                  | Bump             |
|----------------------------------------------|------------------|
| New CLI subcommand (additive)                | minor            |
| New flag on existing command (additive)      | minor            |
| Changed meaning of an existing flag          | major            |
| New badge / finding severity                 | minor            |
| New fixture                                  | patch            |
| Doc-only, no behavior change                 | no bump (CHANGELOG only) |
| Bug fix in audit/compat/gate logic           | patch            |

## Cutting a Release

```bash
# 0. Verify everything green
pytest -q
gitea-forgejo-migrator audit fixtures/systemd-postgres-nginx-audit.json

# 1. Bump version in setup.cfg + CHANGELOG.md
#    (and reference the new section in the [Unreleased] link at the
#    bottom of CHANGELOG.md)

# 2. Commit the version bump
git commit -am 'chore(release): cut v0.1.0-alpha.1'

# 3. Tag
git tag -a v0.1.0-alpha.1 -m 'v0.1.0-alpha.1: alpha preflight and staging plan'

# 4. Push
git push origin main
git push origin v0.1.0-alpha.1

# 5. Build wheel + sdist and (optionally) upload to PyPI
python -m build
# twine upload dist/gitea_forgejo_migrator-0.1.0a1-*
```

## Pre-Release Checklist

- [ ] `pytest -q` is green (61+ tests).
- [ ] `gitea-forgejo-migrator audit fixtures/systemd-postgres-nginx-audit.json` says
      `ready: yes`.
- [ ] `gitea-forgejo-migrator gate fixtures/systemd-postgres-nginx-audit.json --target forgejo-10`
      returns `allowed: yes`.
- [ ] `gitea-forgejo-migrator gate fixtures/systemd-postgres-nginx-audit.json --target forgejo-current`
      returns `allowed: no` (correct refusal).
- [ ] `gitea-forgejo-migrator compatibility --version 1.22.0` says
      `supported: true`.
- [ ] `pip install .` in a fresh venv succeeds and produces the
      `gitea-forgejo-migrator` console script.

## Post-Release Checklist

- [ ] Tag is annotated and pushed.
- [ ] GitHub release notes copy the matching CHANGELOG section.
- [ ] If published to PyPI, the uploaded artifact matches the tag.
- [ ] The `pip install git+https://github.com/...@<tag>` instructions
      in this README work from a fresh checkout.
