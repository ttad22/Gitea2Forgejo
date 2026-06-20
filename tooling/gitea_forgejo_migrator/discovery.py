from __future__ import annotations

import configparser
import re
from pathlib import PurePosixPath

from .models import DeploymentAudit, FeatureUsage, HostArtifact, ResourceUsage, ServiceTopology
from .shell import ShellRunner


def _parse_app_ini(text: str) -> dict[str, str]:
    parser = configparser.ConfigParser()
    parser.read_string("[root]\n" + text)
    root = dict(parser["root"])
    root.update({f"{section}.{k}": v for section in parser.sections() for k, v in parser[section].items()})
    return root


def _size_mb(raw: str) -> float:
    value = raw.strip()
    if not value:
        return 0.0
    number = float("".join(ch for ch in value if ch.isdigit() or ch == ".") or "0")
    suffix = value[-1].upper()
    if suffix == "K":
        return number / 1024.0
    if suffix == "M":
        return number
    if suffix == "G":
        return number * 1024.0
    if suffix == "T":
        return number * 1024.0 * 1024.0
    return number / (1024.0 * 1024.0)


def _count(runner: ShellRunner, database_name: str, sql: str) -> int:
    out = runner.check(f"sudo -u postgres psql -d {sh_quote(database_name)} -Atc {sql!r}")
    return int(out.strip() or "0")


def _du_mb_if_exists(runner: ShellRunner, path: str) -> float:
    command = f"if test -e {sh_quote(path)}; then du -sh {sh_quote(path)} | cut -f1; else echo 0; fi"
    return _size_mb(runner.check(command))


def _is_absolute_unix_path(value: str) -> bool:
    candidate = value.strip()
    return candidate.startswith("/") and "://" not in candidate


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "artifact"


def _add_artifact(
    artifacts: list[HostArtifact],
    seen: set[tuple[str, str | None]],
    *,
    artifact_id: str,
    category: str,
    kind: str,
    decision: str,
    source: str,
    reason: str,
    path: str | None = None,
    details: dict[str, str] | None = None,
    required: bool = False,
) -> None:
    marker = (artifact_id, path)
    if marker in seen:
        return
    seen.add(marker)
    artifacts.append(
        HostArtifact(
            artifact_id=artifact_id,
            category=category,
            kind=kind,
            decision=decision,
            source=source,
            reason=reason,
            path=path,
            details=details or {},
            required=required,
        )
    )


def _existing_path_kind(runner: ShellRunner, path: str) -> str | None:
    if runner.run(f"test -d {sh_quote(path)}").returncode == 0:
        return "directory"
    if runner.run(f"test -f {sh_quote(path)}").returncode == 0:
        return "file"
    return None


def _extract_absolute_paths(text: str) -> list[str]:
    return sorted({match.group(0) for match in re.finditer(r"/[A-Za-z0-9_./@:+-]+", text)})


def _discover_preserve_paths(
    runner: ShellRunner,
    config: dict[str, str],
    *,
    app_ini_path: str,
    data_root: str,
) -> list[str]:
    static_covered_paths = {
        PurePosixPath(app_ini_path),
        PurePosixPath(data_root),
        PurePosixPath(f"{data_root}/custom"),
        PurePosixPath(f"{data_root}/data"),
        PurePosixPath(f"{data_root}/lfs"),
        PurePosixPath(f"{data_root}/log"),
    }
    discovered: list[str] = []
    seen: set[tuple[str, str]] = set()
    for key in sorted(config):
        value = (config.get(key) or "").strip()
        if not _is_absolute_unix_path(value):
            continue
        path = PurePosixPath(value)
        if path in static_covered_paths:
            continue
        kind = _existing_path_kind(runner, value)
        if not kind:
            continue
        marker = (kind, value)
        if marker in seen:
            continue
        seen.add(marker)
        discovered.append(f"preserve_path:{kind}:{key}={value}")
    return discovered


def _discover_preserve_artifacts(
    runner: ShellRunner,
    config: dict[str, str],
    *,
    app_ini_path: str,
    data_root: str,
) -> list[HostArtifact]:
    artifacts: list[HostArtifact] = []
    seen: set[tuple[str, str | None]] = set()
    for note in _discover_preserve_paths(runner, config, app_ini_path=app_ini_path, data_root=data_root):
        payload = note[len("preserve_path:") :]
        kind, remainder = payload.split(":", 1)
        key, path = remainder.split("=", 1)
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"config_{_slug(key)}",
            category="config_path",
            kind=kind,
            decision="adopted",
            source=f"app_ini:{key}",
            reason="Absolute filesystem path declared in app.ini and present on disk.",
            path=path,
            required=False,
        )
    return artifacts


def _infer_authorized_keys_file(
    runner: ShellRunner,
    config: dict[str, str],
    *,
    data_root: str,
) -> str:
    configured = (config.get("server.ssh_authorized_keys_file") or "").strip()
    if configured:
        return configured
    run_user = (config.get("run_user") or "git").strip() or "git"
    candidates = [
        f"{data_root}/git/.ssh/authorized_keys",
        f"{data_root}/.ssh/authorized_keys",
        f"/home/{run_user}/.ssh/authorized_keys",
    ]
    for candidate in candidates:
        if runner.run(f"test -f {sh_quote(candidate)}").returncode == 0:
            return candidate
    return candidates[0]


def _collect_service_artifacts(
    runner: ShellRunner,
    service_name: str,
) -> list[HostArtifact]:
    artifacts: list[HostArtifact] = []
    seen: set[tuple[str, str | None]] = set()
    fragment_path = runner.check(f"systemctl show -p FragmentPath --value {sh_quote(service_name)} || true").strip()
    if fragment_path:
        _add_artifact(
            artifacts,
            seen,
            artifact_id="systemd_fragment",
            category="systemd",
            kind="file",
            decision="preserved_external",
            source="systemctl:FragmentPath",
            reason="Primary systemd unit file controls service startup semantics.",
            path=fragment_path,
        )
    drop_in_paths = runner.check(f"systemctl show -p DropInPaths --value {sh_quote(service_name)} || true").strip()
    for index, path in enumerate(filter(None, drop_in_paths.split(":"))):
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"systemd_dropin_{index}",
            category="systemd",
            kind="file",
            decision="manual_review",
            source="systemctl:DropInPaths",
            reason="Systemd drop-in may override runtime flags, environment, or limits.",
            path=path,
        )
    unit_text = runner.check(f"systemctl cat {sh_quote(service_name)} || true")
    for line in unit_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("EnvironmentFile="):
            if stripped.startswith(("ExecStartPre=", "ExecStartPost=", "ExecReload=")):
                for path in _extract_absolute_paths(stripped.split("=", 1)[1]):
                    _add_artifact(
                        artifacts,
                        seen,
                        artifact_id=f"systemd_exec_{_slug(path)}",
                        category="systemd",
                        kind="script",
                        decision="manual_review",
                        source="systemctl:ExecHook",
                        reason="Systemd hook references a host-side script used during service lifecycle.",
                        path=path,
                    )
            continue
        env_file = stripped.split("=", 1)[1].strip().lstrip("-").strip()
        if env_file and env_file.startswith("/"):
            _add_artifact(
                artifacts,
                seen,
                artifact_id=f"systemd_env_{_slug(env_file)}",
                category="systemd",
                kind="file",
                decision="manual_review",
                source="systemctl:EnvironmentFile",
                reason="Environment file may inject secrets or non-default runtime paths.",
                path=env_file,
            )
    return artifacts


def _collect_nginx_artifacts(
    runner: ShellRunner,
    *,
    domain: str,
    root_url: str,
    service_name: str,
    app_port: str = "3000",
) -> list[HostArtifact]:
    artifacts: list[HostArtifact] = []
    seen: set[tuple[str, str | None]] = set()
    url_host = root_url.replace("https://", "").replace("http://", "").split("/", 1)[0]
    search_terms = [term for term in [domain, url_host, service_name, "gitea", "forgejo", app_port] if term]
    if not search_terms:
        return artifacts
    pattern = "|".join(re.escape(term) for term in search_terms)
    command = (
        "grep -RIl -E "
        + sh_quote(pattern)
        + " /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/nginx/sites-available 2>/dev/null || true"
    )
    for index, path in enumerate(filter(None, runner.check(command).splitlines())):
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"nginx_config_{index}",
            category="nginx",
            kind="file",
            decision="preserved_external",
            source="nginx:grep",
            reason="Nginx config references the Gitea/Forgejo virtual host or upstream.",
            path=path,
        )
        content = runner.check(f"sed -n '1,240p' {sh_quote(path)} || true")
        for directive in ("ssl_certificate", "ssl_certificate_key"):
            for match in re.finditer(rf"{directive}\s+([^;]+);", content):
                referenced = match.group(1).strip()
                if not referenced.startswith("/"):
                    continue
                _add_artifact(
                    artifacts,
                    seen,
                    artifact_id=f"nginx_{directive}_{_slug(referenced)}",
                    category="tls",
                    kind="file",
                    decision="manual_review",
                    source=f"nginx:{directive}",
                    reason="TLS material is external to Forgejo and must remain available after cutover.",
                    path=referenced,
                )
        for match in re.finditer(r"include\s+([^;]+);", content):
            referenced = match.group(1).strip()
            if not referenced.startswith("/"):
                continue
            _add_artifact(
                artifacts,
                seen,
                artifact_id=f"nginx_include_{_slug(referenced)}",
                category="nginx",
                kind="file",
                decision="preserved_external",
                source="nginx:include",
                reason="Included nginx snippet participates in the Gitea/Forgejo proxy configuration.",
                path=referenced,
            )
    return artifacts


def _collect_cron_artifacts(
    runner: ShellRunner,
    *,
    search_terms: list[str],
) -> list[HostArtifact]:
    artifacts: list[HostArtifact] = []
    seen: set[tuple[str, str | None]] = set()
    pattern = "|".join(re.escape(term) for term in search_terms if term)
    if not pattern:
        return artifacts
    command = (
        "grep -RIl -E "
        + sh_quote(pattern)
        + " /etc/crontab /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly 2>/dev/null || true"
    )
    for index, path in enumerate(filter(None, runner.check(command).splitlines())):
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"cron_file_{index}",
            category="cron",
            kind="file",
            decision="manual_review",
            source="cron:filesystem",
            reason="Cron job references Gitea/Forgejo paths or hostnames and may need continuity after cutover.",
            path=path,
        )
        content = runner.check(f"sed -n '1,240p' {sh_quote(path)} || true")
        for referenced in _extract_absolute_paths(content):
            if referenced.startswith(("/etc/gitea", "/usr/local", "/opt", "/srv", "/var/lib/gitea")):
                _add_artifact(
                    artifacts,
                    seen,
                    artifact_id=f"cron_script_{_slug(referenced)}",
                    category="cron",
                    kind="script",
                    decision="manual_review",
                    source="cron:referenced_path",
                    reason="Cron entry references a host-side path that may be part of operational glue.",
                    path=referenced,
                )
    for user in ("git", "gitea", "forgejo", "root"):
        result = runner.run(f"crontab -u {sh_quote(user)} -l 2>/dev/null")
        if result.returncode != 0 or not re.search(pattern, result.stdout, flags=re.IGNORECASE):
            continue
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"crontab_{user}",
            category="cron",
            kind="crontab",
            decision="manual_review",
            source=f"crontab:{user}",
            reason="Per-user crontab references Gitea/Forgejo and should be reviewed after migration.",
            details={"user": user},
            required=False,
        )
        for referenced in _extract_absolute_paths(result.stdout):
            if referenced.startswith(("/etc/gitea", "/usr/local", "/opt", "/srv", "/var/lib/gitea")):
                _add_artifact(
                    artifacts,
                    seen,
                    artifact_id=f"crontab_script_{user}_{_slug(referenced)}",
                    category="cron",
                    kind="script",
                    decision="manual_review",
                    source=f"crontab:{user}:referenced_path",
                    reason="Per-user crontab references a host-side Gitea/Forgejo helper path.",
                    path=referenced,
                )
    return artifacts


def _collect_hook_artifacts(
    runner: ShellRunner,
    *,
    repository_root: str,
) -> list[HostArtifact]:
    artifacts: list[HostArtifact] = []
    seen: set[tuple[str, str | None]] = set()
    command = (
        "find "
        + sh_quote(repository_root)
        + " -path '*/hooks/*' -type f ! -name '*.sample' -print 2>/dev/null || true"
    )
    for index, path in enumerate(filter(None, runner.check(command).splitlines())):
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"hook_{index}",
            category="git_hook",
            kind="file",
            decision="manual_review",
            source="repository:hooks",
            reason="Git hooks can contain organization-specific policy or integration logic.",
            path=path,
        )
        content = runner.check(f"sed -n '1,240p' {sh_quote(path)} || true")
        for referenced in _extract_absolute_paths(content):
            if referenced.startswith(("/usr/local", "/opt", "/srv")):
                _add_artifact(
                    artifacts,
                    seen,
                    artifact_id=f"hook_script_{_slug(referenced)}",
                    category="git_hook",
                    kind="script",
                    decision="manual_review",
                    source="repository:hook_reference",
                    reason="Hook script references an external helper that must remain available post-cutover.",
                    path=referenced,
                )
    return artifacts


def _collect_host_script_artifacts(
    runner: ShellRunner,
    *,
    search_terms: list[str],
) -> list[HostArtifact]:
    artifacts: list[HostArtifact] = []
    seen: set[tuple[str, str | None]] = set()
    roots = ["/usr/local/bin", "/usr/local/sbin", "/opt", "/srv"]
    pattern = "|".join(re.escape(term) for term in search_terms if term)
    if not pattern:
        return artifacts
    command = (
        "grep -RIl -m1 -E "
        + sh_quote(pattern)
        + " "
        + " ".join(sh_quote(root) for root in roots)
        + " 2>/dev/null || true"
    )
    for index, path in enumerate(filter(None, runner.check(command).splitlines())):
        _add_artifact(
            artifacts,
            seen,
            artifact_id=f"host_script_{index}",
            category="host_script",
            kind="file",
            decision="manual_review",
            source="filesystem_scan",
            reason="Host-side script references Gitea/Forgejo and may need to remain intact post-cutover.",
            path=path,
        )
    return artifacts


def _collect_host_artifacts(
    runner: ShellRunner,
    config: dict[str, str],
    *,
    app_ini_path: str,
    data_root: str,
    service_name: str,
    repository_root: str,
    domain: str,
    root_url: str,
) -> list[HostArtifact]:
    search_terms = [
        domain,
        root_url,
        service_name,
        "gitea",
        "forgejo",
        repository_root,
        data_root,
    ]
    artifacts: list[HostArtifact] = []
    for scanner in (
        lambda: _discover_preserve_artifacts(runner, config, app_ini_path=app_ini_path, data_root=data_root),
        lambda: _collect_service_artifacts(runner, service_name),
        lambda: _collect_nginx_artifacts(runner, domain=domain, root_url=root_url, service_name=service_name),
        lambda: _collect_cron_artifacts(runner, search_terms=search_terms),
        lambda: _collect_hook_artifacts(runner, repository_root=repository_root),
        lambda: _collect_host_script_artifacts(runner, search_terms=search_terms),
    ):
        artifacts.extend(scanner())
    return artifacts


def collect_live_audit(
    runner: ShellRunner,
    app_ini_path: str = "/etc/gitea/app.ini",
    data_root: str = "/var/lib/gitea",
) -> DeploymentAudit:
    hostname = runner.check("hostname")
    app_ini = runner.check(f"sed -n '1,240p' {sh_quote(app_ini_path)}")
    config = _parse_app_ini(app_ini)
    gitea_version_raw = runner.check("gitea --version 2>/dev/null || forgejo --version 2>/dev/null")
    database_name = config.get("database.name", "gitea") or "gitea"
    postgres_version = runner.check(f"sudo -u postgres psql -d {sh_quote(database_name)} -Atc 'select version();'")
    nginx_active = runner.check("systemctl is-active nginx")
    gitea_active = runner.check("systemctl is-active gitea || systemctl is-active forgejo")
    _ = (nginx_active, gitea_active)

    root_free = runner.check("df -BG / | awk 'NR==2 {gsub(/G/, \"\", $4); print $4}'")
    repo_path = config.get("repository.root", f"{data_root}/data/gitea-repositories") or f"{data_root}/data/gitea-repositories"
    attachments_path = config.get("attachment.path", f"{data_root}/data/attachments") or f"{data_root}/data/attachments"
    lfs_path = config.get("server.lfs_content_path", f"{data_root}/lfs") or f"{data_root}/lfs"
    packages_path = config.get("packages.path", f"{data_root}/data/packages") or f"{data_root}/data/packages"
    total_path = data_root
    domain = config.get("server.domain", "")
    root_url = config.get("server.root_url", "")
    service_name = "gitea"

    total_mb = _du_mb_if_exists(runner, total_path)
    repo_mb = _du_mb_if_exists(runner, repo_path)
    attachments_mb = _du_mb_if_exists(runner, attachments_path)
    lfs_mb = _du_mb_if_exists(runner, lfs_path)
    packages_mb = _du_mb_if_exists(runner, packages_path)

    service = ServiceTopology(
        install_mode="systemd-binary",
        reverse_proxy="nginx",
        database="postgresql",
        app_service_name="gitea",
        ssh_mode="host-sshd" if config.get("server.start_ssh_server", "false").lower() == "false" else "embedded-ssh",
    )
    resources = ResourceUsage(
        root_free_gb=float(root_free),
        gitea_total_mb=round(total_mb, 3),
        repositories_mb=round(repo_mb, 3),
        attachments_mb=round(attachments_mb, 3),
        lfs_mb=round(lfs_mb, 3),
        packages_mb=round(packages_mb, 3),
    )
    features = FeatureUsage(
        repositories=_count(runner, database_name, "select count(*) from repository;"),
        users=_count(runner, database_name, 'select count(*) from "user";'),
        org_memberships=_count(runner, database_name, 'select count(*) from "org_user";'),
        lfs_objects=_count(runner, database_name, "select count(*) from lfs_meta_object;"),
        action_runs=_count(runner, database_name, "select count(*) from action_run;"),
        action_runners=_count(runner, database_name, "select count(*) from action_runner;"),
        packages=_count(runner, database_name, "select count(*) from package;"),
    )
    host_artifacts = _collect_host_artifacts(
        runner,
        config,
        app_ini_path=app_ini_path,
        data_root=data_root,
        service_name=service_name,
        repository_root=repo_path,
        domain=domain,
        root_url=root_url,
    )
    return DeploymentAudit(
        name=hostname,
        host=runner.ssh_target or "localhost",
        gitea_version=gitea_version_raw.split()[2] if "version" in gitea_version_raw else gitea_version_raw,
        postgres_version=postgres_version,
        app_ini_path=app_ini_path,
        data_root=data_root,
        service=service,
        resources=resources,
        features=features,
        notes=[
            f"domain={domain}",
            f"root_url={root_url}",
            f"lfs_start_server={config.get('server.lfs_start_server', '')}",
            f"ssh_authorized_keys_file={_infer_authorized_keys_file(runner, config, data_root=data_root)}",
            f"database_name={database_name}",
            f"repository_root={repo_path}",
            f"attachments_path={attachments_path}",
            f"packages_path={packages_path}",
            *_discover_preserve_paths(runner, config, app_ini_path=app_ini_path, data_root=data_root),
        ],
        host_artifacts=host_artifacts,
    )


def sh_quote(path: str) -> str:
    return "'" + path.replace("'", "'\"'\"'") + "'"
