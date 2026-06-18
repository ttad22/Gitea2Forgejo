from __future__ import annotations

from .models import AuditFinding, DeploymentAuditOutcome, DeploymentAuditReport


def evaluate_deployment(report: DeploymentAuditReport) -> DeploymentAuditOutcome:
    findings: list[AuditFinding] = []
    ready = True
    risk_level = "low"

    if not report.internal_ssh_server:
        findings.append(
            AuditFinding(
                code="ssh-mode",
                severity="info",
                summary="Host SSH is authoritative; preserve host sshd behavior during migration.",
            )
        )

    if report.service_model != "systemd":
        findings.append(
            AuditFinding(
                code="service-model",
                severity="warning",
                summary=f"Non-reference service model detected: {report.service_model}.",
            )
        )
        risk_level = "medium"

    if report.database_backend != "postgresql":
        findings.append(
            AuditFinding(
                code="database-backend",
                severity="warning",
                summary=f"Non-reference database backend detected: {report.database_backend}.",
            )
        )
        risk_level = "medium"

    if report.actions_runs or report.action_runners:
        findings.append(
            AuditFinding(
                code="actions-usage",
                severity="warning",
                summary="Actions usage detected; validate Forgejo action behavior explicitly.",
            )
        )
        risk_level = "medium"

    if report.packages:
        findings.append(
            AuditFinding(
                code="packages-usage",
                severity="warning",
                summary="Packages are in use; package endpoints need explicit post-cutover checks.",
            )
        )
        risk_level = "medium"

    if report.lfs_objects or report.lfs_enabled:
        if report.lfs_objects:
            findings.append(
                AuditFinding(
                    code="lfs-usage",
                    severity="warning",
                    summary="LFS objects present; verify LFS storage path and endpoint behavior.",
                )
            )
            risk_level = "medium"

    if report.root_free_gb < 10.0:
        findings.append(
            AuditFinding(
                code="disk-headroom",
                severity="blocker",
                summary="Insufficient free disk headroom for safe staged migration and backup artifacts.",
            )
        )
        ready = False
        risk_level = "high"

    return DeploymentAuditOutcome(ready=ready, risk_level=risk_level, findings=findings)
