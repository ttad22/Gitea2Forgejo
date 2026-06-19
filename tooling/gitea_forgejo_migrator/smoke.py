from __future__ import annotations

import ipaddress

from .models import DeploymentAudit, SmokeCheck, SmokePlan


def _audit_note_value(audit: DeploymentAudit, key: str) -> str:
    prefix = f"{key}="
    for note in audit.notes:
        if note.startswith(prefix):
            return note[len(prefix) :].strip()
    return ""


def _infer_external_host(audit: DeploymentAudit) -> str:
    domain = _audit_note_value(audit, "domain")
    if domain:
        return domain
    root_url = _audit_note_value(audit, "root_url")
    if root_url:
        host = root_url.split("://", 1)[-1].split("/", 1)[0]
        if host:
            return host
    try:
        ipaddress.ip_address(audit.host)
    except ValueError:
        return audit.host
    return ""


def build_smoke_plan(audit: DeploymentAudit) -> SmokePlan:
    domain = _infer_external_host(audit)
    checks = [
        SmokeCheck("service_app", f"systemctl is-active {audit.service.app_service_name}"),
        SmokeCheck("service_proxy", "systemctl is-active nginx"),
        SmokeCheck("service_db", "systemctl is-active postgresql"),
        SmokeCheck("web_health", f"curl -fsS http://127.0.0.1:3000/api/health"),
        SmokeCheck("root_ui", f"curl -fsSI http://127.0.0.1:80/ | head -n 1"),
        SmokeCheck("ssh_port", "ss -ltn | grep -q ':22 '"),
    ]
    if domain:
        checks.extend(
            [
                SmokeCheck("https_root", f"curl -fsSI https://{domain}/ | head -n 1", critical=False),
                SmokeCheck(
                    "https_repo_browse",
                    f"curl -fsSI https://{domain}/explore/repos | head -n 1",
                    critical=False,
                ),
            ]
        )
    return SmokePlan(deployment_name=audit.name, checks=checks)
