from __future__ import annotations

import unittest

from gitea_forgejo_migrator.discovery import _parse_app_ini, _size_mb


class DiscoveryTests(unittest.TestCase):
    def test_parse_app_ini_extracts_section_values(self) -> None:
        config = _parse_app_ini(
            "WORK_PATH = /var/lib/gitea\n\n[server]\nDOMAIN = git.tttmsp.com\n"
        )
        self.assertEqual(config["work_path"], "/var/lib/gitea")
        self.assertEqual(config["server.domain"], "git.tttmsp.com")

    def test_size_mb_handles_gigabytes(self) -> None:
        self.assertEqual(_size_mb("1.5G"), 1536.0)
        self.assertEqual(_size_mb("80M"), 80.0)


if __name__ == "__main__":
    unittest.main()
