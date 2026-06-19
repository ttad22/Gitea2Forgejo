from __future__ import annotations

import configparser
from pathlib import PurePosixPath

from .models import DeploymentAudit, FeatureUsage, ResourceUsage, ServiceTopology
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
        if runner.run(f"test -d {sh_quote(value)}").returncode == 0:
            kind = "directory"
        elif runner.run(f"test -f {sh_quote(value)}").returncode == 0:
            kind = "file"
        else:
            continue
        marker = (kind, value)
        if marker in seen:
            continue
        seen.add(marker)
        discovered.append(f"preserve_path:{kind}:{key}={value}")
    return discovered


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
            f"domain={config.get('server.domain', '')}",
            f"root_url={config.get('server.root_url', '')}",
            f"lfs_start_server={config.get('server.lfs_start_server', '')}",
            f"ssh_authorized_keys_file={config.get('server.ssh_authorized_keys_file', '')}",
            f"database_name={database_name}",
            f"repository_root={repo_path}",
            f"attachments_path={attachments_path}",
            f"packages_path={packages_path}",
            *_discover_preserve_paths(runner, config, app_ini_path=app_ini_path, data_root=data_root),
        ],
    )


def sh_quote(path: str) -> str:
    return "'" + path.replace("'", "'\"'\"'") + "'"
