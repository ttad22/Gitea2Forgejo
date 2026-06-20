from __future__ import annotations

import unittest

from gitea_forgejo_migrator.discovery import (
    _collect_cron_artifacts,
    _collect_hook_artifacts,
    _collect_host_script_artifacts,
    _collect_nginx_artifacts,
    _collect_service_artifacts,
    _discover_preserve_paths,
    _parse_app_ini,
    _size_mb,
)


class DiscoveryTests(unittest.TestCase):
    def test_parse_app_ini_extracts_section_values(self) -> None:
        config = _parse_app_ini(
            "WORK_PATH = /var/lib/gitea\n\n[server]\nDOMAIN = git.example.org\n\n[database]\nNAME = codeforge\n\n[repository]\nROOT = /srv/git/repositories\n"
        )
        self.assertEqual(config["work_path"], "/var/lib/gitea")
        self.assertEqual(config["server.domain"], "git.example.org")
        self.assertEqual(config["database.name"], "codeforge")
        self.assertEqual(config["repository.root"], "/srv/git/repositories")

    def test_size_mb_handles_gigabytes(self) -> None:
        self.assertEqual(_size_mb("1.5G"), 1536.0)
        self.assertEqual(_size_mb("80M"), 80.0)

    def test_discover_preserve_paths_harvests_existing_absolute_paths(self) -> None:
        class FakeRunner:
            def run(self, command: str):
                mapping = {
                    "test -d '/srv/git/repositories'": 0,
                    "test -d '/srv/git/certs/server.crt'": 1,
                    "test -f '/srv/git/certs/server.crt'": 0,
                    "test -d '/var/lib/gitea/data'": 0,
                }
                return type("Result", (), {"returncode": mapping.get(command, 1)})()

        config = {
            "repository.root": "/srv/git/repositories",
            "server.cert_file": "/srv/git/certs/server.crt",
            "session.provider_config": "/var/lib/gitea/data",
            "server.root_url": "https://git.example.org/",
        }
        notes = _discover_preserve_paths(
            FakeRunner(),
            config,
            app_ini_path="/etc/gitea/app.ini",
            data_root="/var/lib/gitea",
        )
        self.assertIn("preserve_path:directory:repository.root=/srv/git/repositories", notes)
        self.assertIn("preserve_path:file:server.cert_file=/srv/git/certs/server.crt", notes)
        self.assertNotIn("preserve_path:directory:session.provider_config=/var/lib/gitea/data", notes)

    def test_discover_preserve_paths_infers_default_authorized_keys_file(self) -> None:
        class FakeRunner:
            def run(self, command: str):
                mapping = {
                    "test -f '/var/lib/gitea/git/.ssh/authorized_keys'": 0,
                }
                return type("Result", (), {"returncode": mapping.get(command, 1)})()

        from gitea_forgejo_migrator.discovery import _infer_authorized_keys_file

        inferred = _infer_authorized_keys_file(
            FakeRunner(),
            {"run_user": "git"},
            data_root="/var/lib/gitea",
        )
        self.assertEqual(inferred, "/var/lib/gitea/git/.ssh/authorized_keys")

    def test_collect_service_artifacts_discovers_dropins_and_env_files(self) -> None:
        class FakeRunner:
            def check(self, command: str) -> str:
                mapping = {
                    "systemctl show -p FragmentPath --value 'gitea' || true": "/etc/systemd/system/gitea.service\n",
                    "systemctl show -p DropInPaths --value 'gitea' || true": "/etc/systemd/system/gitea.service.d/override.conf\n",
                    "systemctl cat 'gitea' || true": "[Service]\nEnvironmentFile=/etc/default/gitea\nExecStartPre=/usr/local/bin/gitea-preflight.sh\n",
                }
                return mapping[command].strip()

        artifacts = _collect_service_artifacts(FakeRunner(), "gitea")
        ids = {item.artifact_id for item in artifacts}
        self.assertIn("systemd_fragment", ids)
        self.assertIn("systemd_dropin_0", ids)
        self.assertIn("systemd_env_etc_default_gitea", ids)
        self.assertIn("systemd_exec_usr_local_bin_gitea_preflight_sh", ids)

    def test_collect_nginx_artifacts_discovers_config_and_tls_paths(self) -> None:
        class FakeRunner:
            def check(self, command: str) -> str:
                if command.startswith("grep -RIl -E "):
                    return "/etc/nginx/sites-enabled/git.conf\n"
                if command == "sed -n '1,240p' '/etc/nginx/sites-enabled/git.conf' || true":
                    return (
                        "server {\n"
                        "  server_name git.example.org;\n"
                        "  include /etc/nginx/snippets/gitea-proxy.conf;\n"
                        "  ssl_certificate /etc/letsencrypt/live/git.example.org/fullchain.pem;\n"
                        "  ssl_certificate_key /etc/letsencrypt/live/git.example.org/privkey.pem;\n"
                        "  proxy_pass http://127.0.0.1:3000;\n"
                        "}\n"
                    )
                raise KeyError(command)

        artifacts = _collect_nginx_artifacts(
            FakeRunner(),
            domain="git.example.org",
            root_url="https://git.example.org/",
            service_name="gitea",
        )
        paths = {item.path for item in artifacts}
        self.assertIn("/etc/nginx/sites-enabled/git.conf", paths)
        self.assertIn("/etc/nginx/snippets/gitea-proxy.conf", paths)
        self.assertIn("/etc/letsencrypt/live/git.example.org/fullchain.pem", paths)
        self.assertIn("/etc/letsencrypt/live/git.example.org/privkey.pem", paths)

    def test_collect_cron_artifacts_discovers_files_and_user_crontab(self) -> None:
        class FakeRunner:
            def check(self, command: str) -> str:
                if command.startswith("grep -RIl -E "):
                    return "/etc/cron.d/gitea-backup\n"
                if command == "sed -n '1,240p' '/etc/cron.d/gitea-backup' || true":
                    return "*/15 * * * * git /usr/local/bin/gitea-backup.sh --config /etc/gitea/app.ini\n"
                raise KeyError(command)

            def run(self, command: str):
                if command == "crontab -u 'git' -l 2>/dev/null":
                    return type("Result", (), {"returncode": 0, "stdout": "*/15 * * * * /usr/local/bin/gitea-backup.sh\n"})()
                return type("Result", (), {"returncode": 1, "stdout": ""})()

        artifacts = _collect_cron_artifacts(FakeRunner(), search_terms=["gitea", "/etc/gitea/app.ini"])
        ids = {item.artifact_id for item in artifacts}
        self.assertIn("cron_file_0", ids)
        self.assertIn("crontab_git", ids)
        self.assertIn("cron_script_usr_local_bin_gitea_backup_sh", ids)

    def test_collect_hook_artifacts_discovers_non_sample_hooks(self) -> None:
        class FakeRunner:
            def check(self, command: str) -> str:
                if command.startswith("find "):
                    return "/srv/git/repositories/org/repo.git/hooks/post-receive\n"
                return "#!/bin/sh\n/usr/local/bin/gitea-deploy-hook \"$@\"\n"

        artifacts = _collect_hook_artifacts(FakeRunner(), repository_root="/srv/git/repositories")
        paths = {item.path for item in artifacts}
        self.assertIn("/srv/git/repositories/org/repo.git/hooks/post-receive", paths)
        self.assertIn("/usr/local/bin/gitea-deploy-hook", paths)

    def test_collect_host_script_artifacts_discovers_gitea_referencing_scripts(self) -> None:
        class FakeRunner:
            def check(self, command: str) -> str:
                return "/usr/local/bin/gitea-backup.sh\n/opt/ops/gitea-sync.sh\n"

        artifacts = _collect_host_script_artifacts(FakeRunner(), search_terms=["gitea", "/var/lib/gitea"])
        paths = {item.path for item in artifacts}
        self.assertIn("/usr/local/bin/gitea-backup.sh", paths)
        self.assertIn("/opt/ops/gitea-sync.sh", paths)


if __name__ == "__main__":
    unittest.main()
