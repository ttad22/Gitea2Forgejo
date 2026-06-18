from __future__ import annotations

import unittest

from gitea_forgejo_migrator.compatibility import assess_gitea_to_forgejo


class CompatibilityTests(unittest.TestCase):
    def test_gitea_122_is_supported(self) -> None:
        result = assess_gitea_to_forgejo("1.22.0")
        self.assertTrue(result.supported)
        self.assertEqual(result.recommended_stages, ["forgejo-10.x", "forgejo-current"])

    def test_gitea_123_is_blocked(self) -> None:
        result = assess_gitea_to_forgejo("1.23.0")
        self.assertFalse(result.supported)
        self.assertEqual(result.recommended_stages, [])


if __name__ == "__main__":
    unittest.main()
