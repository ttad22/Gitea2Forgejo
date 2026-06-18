from __future__ import annotations

from .models import DeploymentAudit, SmokeCheck, SmokePlan


def build_smoke_plan(audit: DeploymentAudit) -> SmokePlan:
    domain = "git.tttmsp.com"
    checks = [
        SmokeCheck("service_app", f"systemctl is-active {audit.service.app_service_name}"),
        SmokeCheck("service_proxy", "systemctl is-active nginx"),
        SmokeCheck("service_db", "systemctl is-active postgresql"),
        SmokeCheck("web_health", "curl -fsS http://127.0.0.1:3000/api/health"),
        SmokeCheck("root_ui", "curl -fsSI http://127.0.0.1:80/ | head -n 1"),
        SmokeCheck("https_root", f"curl -fsSI https://{domain}/ | head -n 1", critical=False),
        SmokeCheck(
            "https_repo_browse",
            f"curl -fsSI https://{domain}/explore/repos | head -n 1",
            critical=False,
        ),
        SmokeCheck("ssh_port", "ss -ltn | grep -q ':22 '"),
    ]
    return SmokePlan(deployment_name=audit.name, checks=checks)
