from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import DeploymentAuditReport


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class AuditOutcome:
    ready: bool
    risk_level: str
    findings: tuple[AuditFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "risk_level": self.risk_level,
            "findings": [asdict(finding) for finding in self.findings],
        }


def _required_free_space_gb(report: DeploymentAuditReport) -> float:
    data_gb = report.total_data_mb / 1024.0
    return max(5.0, round((data_gb * 2.5) + 1.0, 2))


def evaluate_deployment(report: DeploymentAuditReport) -> AuditOutcome:
    findings: list[AuditFinding] = []

    if report.service_model != "systemd":
        findings.append(
            AuditFinding(
                severity="warning",
                code="service-model",
                message=(
                    f"Service model '{report.service_model}' is outside the current same-host "
                    "reference path built around systemd."
                ),
            )
        )

    if report.database_backend not in {"postgres", "postgresql"}:
        findings.append(
            AuditFinding(
                severity="warning",
                code="database-backend",
                message=(
                    f"Database backend '{report.database_backend}' is not the preferred PostgreSQL "
                    "cohort used by the reference migration path."
                ),
            )
        )

    if not report.config_path.startswith("/"):
        findings.append(
            AuditFinding(
                severity="blocker",
                code="config-path",
                message="Config path must be absolute so backup and rollback steps are deterministic.",
            )
        )

    if not report.data_root.startswith("/"):
        findings.append(
            AuditFinding(
                severity="blocker",
                code="data-root",
                message="Data root must be absolute so backup and rollback steps are deterministic.",
            )
        )

    if report.reverse_proxy != "nginx":
        findings.append(
            AuditFinding(
                severity="warning",
                code="reverse-proxy",
                message=(
                    f"Reverse proxy '{report.reverse_proxy}' differs from the reference nginx-based "
                    "cutover plan."
                ),
            )
        )

    if report.reverse_proxy_port == report.app_port:
        findings.append(
            AuditFinding(
                severity="warning",
                code="port-layout",
                message="Reverse proxy port matches the app port; verify that cutover preserves clone URLs.",
            )
        )

    required_free_gb = _required_free_space_gb(report)
    if report.root_free_gb < required_free_gb:
        findings.append(
            AuditFinding(
                severity="blocker",
                code="disk-headroom",
                message=(
                    f"Free disk headroom {report.root_free_gb:.2f} GB is below the estimated "
                    f"backup threshold of {required_free_gb:.2f} GB."
                ),
            )
        )

    if report.actions_runs > 0 or report.action_runners > 0:
        findings.append(
            AuditFinding(
                severity="warning",
                code="actions-usage",
                message="Actions activity is present and should be validated explicitly during migration.",
            )
        )

    if report.packages > 0:
        findings.append(
            AuditFinding(
                severity="warning",
                code="packages-usage",
                message="Package registry data is in use and increases migration validation scope.",
            )
        )

    if report.lfs_enabled and report.lfs_objects > 0:
        findings.append(
            AuditFinding(
                severity="warning",
                code="lfs-usage",
                message="LFS is active with stored objects; include endpoint and object validation in smoke tests.",
            )
        )

    if not report.internal_ssh_server:
        findings.append(
            AuditFinding(
                severity="info",
                code="ssh-mode",
                message="Internal SSH server is disabled; preserve host sshd and SSH clone behavior during cutover.",
            )
        )

    if report.repositories == 0:
        findings.append(
            AuditFinding(
                severity="warning",
                code="empty-instance",
                message="No repositories were reported; verify the audit source before planning migration work.",
            )
        )

    severity_rank = {"info": 0, "warning": 1, "blocker": 2}
    highest = max((severity_rank[finding.severity] for finding in findings), default=0)
    risk_level = {0: "low", 1: "medium", 2: "high"}[highest]
    ready = highest < 2
    return AuditOutcome(ready=ready, risk_level=risk_level, findings=tuple(findings))
