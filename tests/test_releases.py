from __future__ import annotations

from gitea_forgejo_migrator.releases import ReleaseResolver


def test_release_resolver_picks_latest_and_latest_10x(monkeypatch) -> None:
    payload = [
        {
            "tag_name": "v15.0.3",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "forgejo-15.0.3-linux-amd64",
                    "browser_download_url": "https://example.invalid/forgejo-15.0.3-linux-amd64",
                }
            ],
        },
        {
            "tag_name": "v10.0.3",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "forgejo-10.0.3-linux-amd64",
                    "browser_download_url": "https://example.invalid/forgejo-10.0.3-linux-amd64",
                }
            ],
        },
    ]

    monkeypatch.setattr(ReleaseResolver, "_fetch_releases", lambda self: payload)
    bundle = ReleaseResolver().resolve()

    assert bundle.forgejo_current.tag == "v15.0.3"
    assert bundle.forgejo_10.tag == "v10.0.3"
    assert bundle.forgejo_current.asset_url.endswith("15.0.3-linux-amd64")
    assert bundle.forgejo_10.asset_url.endswith("10.0.3-linux-amd64")
