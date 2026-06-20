from __future__ import annotations

import unittest

from gitea_forgejo_migrator.discovery import _discover_preserve_paths, _parse_app_ini, _size_mb


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


if __name__ == "__main__":
    unittest.main()
