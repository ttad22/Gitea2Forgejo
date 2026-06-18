from __future__ import annotations

from dataclasses import asdict, dataclass

from .audit import AuditOutcome
from .models import DeploymentAuditReport


def _parse_version(value: str) -> tuple[int, int, int]:
    cleaned = value.strip()
    parts = cleaned.split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid version '{value}'")

    normalized: list[int] = []
    for part in parts[:3]:
        digits = []
        for character in part:
            if character.isdigit():
                digits.append(character)
            else:
                break
        if not digits:
            raise ValueError(f"Invalid version '{value}'")
        normalized.append(int("".join(digits)))

    while len(normalized) < 3:
        normalized.append(0)
    return tuple(normalized)


@dataclass(frozen=True)
class CompatibilityDecision:
    allowed: bool
    source_kind: str
    source_version: str
    target: str
    recommended_path: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "source_kind": self.source_kind,
            "source_version": self.source_version,
            "target": self.target,
            "recommended_path": list(self.recommended_path),
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
        }


def evaluate_compatibility(
    report: DeploymentAuditReport,
    *,
    target: str,
    audit_outcome: AuditOutcome | None = None,
) -> CompatibilityDecision:
    normalized_target = target.strip().lower()
    if normalized_target not in {"forgejo-10", "forgejo-current"}:
        raise ValueError(f"Unsupported target '{target}'")

    source_version = _parse_version(report.gitea_version)
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if audit_outcome is not None and not audit_outcome.ready:
        blocking_reasons.append("Deployment audit contains blocker-level findings.")

    if source_version[0] != 1:
        blocking_reasons.append("Only Gitea 1.x source cohorts are currently modeled.")
    elif source_version[1] == 22:
        if normalized_target == "forgejo-10":
            pass
        else:
            blocking_reasons.append(
                "Gitea 1.22.x must stage through Forgejo 10 before upgrading to the current Forgejo release."
            )
    elif source_version[1] > 22:
        blocking_reasons.append(
            "Gitea 1.23+ is outside the supported direct migration cohort and must be handled manually."
        )
    else:
        blocking_reasons.append(
            "Only the Gitea 1.22.x migration cohort is currently first-class in this tool."
        )

    if report.actions_runs > 0 or report.packages > 0:
        warnings.append(
            "Feature activity beyond the reference cohort is present; extend post-cutover validation accordingly."
        )

    recommended_path: tuple[str, ...]
    if normalized_target == "forgejo-10":
        recommended_path = ("gitea-1.22.x", "forgejo-10")
    else:
        recommended_path = ("gitea-1.22.x", "forgejo-10", "forgejo-current")

    return CompatibilityDecision(
        allowed=not blocking_reasons,
        source_kind="gitea",
        source_version=report.gitea_version,
        target=normalized_target,
        recommended_path=recommended_path,
        blocking_reasons=tuple(blocking_reasons),
        warnings=tuple(warnings),
    )
