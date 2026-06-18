from __future__ import annotations

from dataclasses import dataclass

from .models import CompatibilityAssessment


@dataclass(frozen=True, slots=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, raw: str) -> "Version":
        parts = raw.strip().split(".")
        if len(parts) < 2:
            raise ValueError(f"invalid version string: {raw!r}")
        nums = [int(part) for part in parts[:3]]
        while len(nums) < 3:
            nums.append(0)
        return cls(nums[0], nums[1], nums[2])


def assess_gitea_to_forgejo(version_str: str) -> CompatibilityAssessment:
    version = Version.parse(version_str)
    base_warning = (
        "Preserve app.ini secrets, database backups, repository data, and "
        "reverse-proxy behavior before replacement."
    )

    if version.major != 1:
        return CompatibilityAssessment(
            source_version=version_str,
            supported=False,
            reason="Only Gitea 1.x source cohorts are currently modeled.",
            recommended_stages=[],
            risk_level="high",
            warnings=[base_warning],
        )

    if version.minor <= 21:
        return CompatibilityAssessment(
            source_version=version_str,
            supported=True,
            reason="Officially compatible source cohort for staged Forgejo upgrade.",
            recommended_stages=["forgejo-10.x", "forgejo-current"],
            risk_level="medium",
            warnings=[
                base_warning,
                "Validate custom assets, LFS path handling, and any older config keys.",
            ],
        )

    if version.minor == 22:
        return CompatibilityAssessment(
            source_version=version_str,
            supported=True,
            reason="Last officially supported Gitea cohort for staged Forgejo upgrade.",
            recommended_stages=["forgejo-10.x", "forgejo-current"],
            risk_level="low",
            warnings=[
                base_warning,
                "Do not skip the Forgejo 10.x stage.",
            ],
        )

    return CompatibilityAssessment(
        source_version=version_str,
        supported=False,
        reason=(
            "Gitea 1.23+ is not covered by the official transparent in-place "
            "Forgejo upgrade path."
        ),
        recommended_stages=[],
        risk_level="high",
        warnings=[
            base_warning,
            "Use repo-by-repo migration or an expert/manual database translation workflow.",
        ],
    )
