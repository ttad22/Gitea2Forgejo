from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitea_forgejo_migrator.executor import MigrationExecutor, MigrationRequest
from gitea_forgejo_migrator.models import DeploymentAudit, FeatureUsage, ResourceUsage, ServiceTopology
from gitea_forgejo_migrator.releases import ForgejoRelease, ReleaseBundle


def _audit() -> DeploymentAudit:
    return DeploymentAudit(
        name="git-ops",
        host="localhost",
        gitea_version="1.22.0",
        postgres_version="PostgreSQL 14.23",
        app_ini_path="/etc/gitea/app.ini",
        data_root="/var/lib/gitea",
        service=ServiceTopology(
            install_mode="systemd-binary",
            reverse_proxy="nginx",
            database="postgresql",
            app_service_name="gitea",
            ssh_mode="host-sshd",
        ),
        resources=ResourceUsage(
            root_free_gb=188.0,
            gitea_total_mb=876.0,
            repositories_mb=795.0,
            attachments_mb=80.0,
            lfs_mb=0.0,
            packages_mb=0.0,
        ),
        features=FeatureUsage(
            repositories=36,
            users=5,
            org_memberships=2,
            lfs_objects=0,
            action_runs=0,
            action_runners=0,
            packages=0,
        ),
        notes=[
            "domain=git.example.org",
            "root_url=https://git.example.org/",
            "lfs_start_server=false",
            "ssh_authorized_keys_file=/var/lib/gitea/.ssh/authorized_keys",
        ],
    )


class FakeRunner:
    def __init__(self, *, fail_after_current_start: bool = False) -> None:
        self.fail_after_current_start = fail_after_current_start
        self.commands: list[str] = []
        self.current_binary_version = "gitea"
        self.started_versions: list[str] = []
        self.rollback_seen = False

    def run(self, command: str):
        self.commands.append(command)
        returncode = 0
        stdout = self._stdout_for(command)
        stderr = ""

        if command == "test -e '/var/lib/gitea/lfs'":
            returncode = 1

        if "install -m 0755" in command and "/releases/forgejo-10/forgejo-10.0.3-linux-amd64" in command:
            self.current_binary_version = "forgejo-10"
        elif "install -m 0755" in command and "/releases/forgejo-current/forgejo-15.0.3-linux-amd64" in command:
            self.current_binary_version = "forgejo-current"
        elif "install -m 0755" in command and "gitea-original.bin" in command:
            self.current_binary_version = "gitea"
            self.rollback_seen = True

        if "systemctl start" in command:
            self.started_versions.append(self.current_binary_version)
            if self.fail_after_current_start and self.current_binary_version == "forgejo-current":
                returncode = 1
                stderr = "simulated start failure"

        if "curl -fsS http://127.0.0.1:3000/api/health" in command and self.fail_after_current_start:
            if self.current_binary_version == "forgejo-current":
                returncode = 1
                stderr = "simulated health failure"

        return type("Result", (), {"stdout": stdout, "stderr": stderr, "returncode": returncode})()

    def check(self, command: str) -> str:
        result = self.run(command)
        if result.returncode != 0:
            raise RuntimeError(f"command failed: {command}\nstderr:\n{result.stderr}")
        return result.stdout.strip()

    def _stdout_for(self, command: str) -> str:
        if command == "command -v gitea":
            return "/usr/local/bin/gitea\n"
        if command == "uname -m":
            return "x86_64\n"
        if command == "hostname":
            return "git-ops\n"
        if command.startswith("curl -fsS http://127.0.0.1:3000/api/health"):
            return '{"status":"ok"}\n'
        if command.startswith("systemctl is-active"):
            return "active\n"
        if command.startswith("ss -ltn"):
            return "LISTEN 0 128 *:22 *:*\n"
        if command.startswith("test -s '/var/lib/gitea/.ssh/authorized_keys'"):
            return ""
        if command.startswith("'/tmp") and command.endswith("--version"):
            if "forgejo-10.0.3-linux-amd64" in command:
                return "Forgejo version 10.0.3 built with go1.22\n"
            if "forgejo-15.0.3-linux-amd64" in command:
                return "Forgejo version 15.0.3 built with go1.23\n"
        return ""


class FakeResolver:
    def resolve(self) -> ReleaseBundle:
        return ReleaseBundle(
            forgejo_10=ForgejoRelease(
                tag="v10.0.3",
                asset_name="forgejo-10.0.3-linux-amd64",
                asset_url="https://downloads.example.org/forgejo-10.0.3-linux-amd64",
            ),
            forgejo_current=ForgejoRelease(
                tag="v15.0.3",
                asset_name="forgejo-15.0.3-linux-amd64",
                asset_url="https://downloads.example.org/forgejo-15.0.3-linux-amd64",
            ),
        )


@pytest.fixture(autouse=True)
def _root_user(monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 0)


@pytest.fixture(autouse=True)
def _fake_audit(monkeypatch):
    monkeypatch.setattr("gitea_forgejo_migrator.executor.collect_live_audit", lambda *args, **kwargs: _audit())


def test_migrate_successful_supported_cohort(tmp_path: Path) -> None:
    runner = FakeRunner()
    executor = MigrationExecutor(runner=runner, release_resolver=FakeResolver())

    outcome = executor.migrate(MigrationRequest(work_root=str(tmp_path), force=False, dry_run=False))

    assert outcome.success is True
    assert outcome.rollback_performed is False
    assert outcome.stages_completed == ("backup", "forgejo-10", "forgejo-current")
    assert Path(outcome.outcome_path).exists()
    payload = json.loads(Path(outcome.outcome_path).read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert any("pg_dump" in command for command in runner.commands)
    assert any("/releases/forgejo-10/forgejo-10.0.3-linux-amd64" in command for command in runner.commands)
    assert any("/releases/forgejo-current/forgejo-15.0.3-linux-amd64" in command for command in runner.commands)
    assert not any("lfs.tar.gz" in command and "tar czf" in command for command in runner.commands)


def test_migrate_rolls_back_on_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_after_current_start=True)
    executor = MigrationExecutor(runner=runner, release_resolver=FakeResolver())

    with pytest.raises(RuntimeError) as excinfo:
        executor.migrate(MigrationRequest(work_root=str(tmp_path), force=False, dry_run=False))

    payload = json.loads(str(excinfo.value))
    assert payload["success"] is False
    assert payload["rollback_performed"] is True
    assert runner.rollback_seen is True
    assert any("pg_restore" in command for command in runner.commands)


def test_migrate_requires_yes_at_cli(tmp_path: Path, capsys) -> None:
    from gitea_forgejo_migrator.cli import main

    exit_code = main(["migrate", "--work-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "refusing to mutate without --yes" in captured.out
