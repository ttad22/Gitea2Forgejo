from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ForgejoRelease:
    tag: str
    asset_name: str
    asset_url: str

    @property
    def version(self) -> str:
        return self.tag.removeprefix("v")


@dataclass(frozen=True, slots=True)
class ReleaseBundle:
    forgejo_10: ForgejoRelease
    forgejo_current: ForgejoRelease


class ReleaseResolver:
    RELEASES_URL = "https://codeberg.org/api/v1/repos/forgejo/forgejo/releases?limit=100"

    def __init__(self, *, arch: str = "amd64", os_name: str = "linux") -> None:
        self.arch = arch
        self.os_name = os_name

    def resolve(self) -> ReleaseBundle:
        releases = self._fetch_releases()
        current = self._pick_release(releases)
        forgejo_10 = self._pick_release(releases, major=10)
        return ReleaseBundle(forgejo_10=forgejo_10, forgejo_current=current)

    def _fetch_releases(self) -> list[dict[str, Any]]:
        with urllib.request.urlopen(self.RELEASES_URL, timeout=30) as response:
            payload = json.load(response)
        if not isinstance(payload, list):
            raise RuntimeError("Forgejo release API returned a non-list payload.")
        return payload

    def _pick_release(self, releases: list[dict[str, Any]], major: int | None = None) -> ForgejoRelease:
        for release in releases:
            if release.get("draft") or release.get("prerelease"):
                continue
            tag = str(release.get("tag_name", ""))
            if not tag.startswith("v"):
                continue
            if major is not None and not tag.startswith(f"v{major}."):
                continue
            asset = self._pick_asset(release)
            if asset is None:
                continue
            return ForgejoRelease(tag=tag, asset_name=asset["name"], asset_url=asset["browser_download_url"])
        cohort = f"{major}.x" if major is not None else "current"
        raise RuntimeError(f"Could not resolve a Forgejo {cohort} release for {self.os_name}/{self.arch}.")

    def _pick_asset(self, release: dict[str, Any]) -> dict[str, Any] | None:
        expected = f"forgejo-{str(release.get('tag_name', '')).removeprefix('v')}-{self.os_name}-{self.arch}"
        for asset in release.get("assets", []):
            if asset.get("name") == expected:
                return asset
        return None
