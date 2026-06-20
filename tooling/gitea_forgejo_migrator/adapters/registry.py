from __future__ import annotations

from ..models import DeploymentAudit
from .base import PlatformAdapter
from .systemd_binary import SystemdBinaryAdapter


class PlatformAdapterRegistry:
    def __init__(self, adapters: list[PlatformAdapter] | None = None) -> None:
        self._adapters = adapters or [SystemdBinaryAdapter()]

    def resolve(self, audit: DeploymentAudit) -> PlatformAdapter:
        for adapter in self._adapters:
            if adapter.supports(audit):
                return adapter
        raise RuntimeError(
            "unsupported deployment cohort: no platform adapter matched "
            f"install_mode={audit.service.install_mode}, "
            f"database={audit.service.database}, "
            f"reverse_proxy={audit.service.reverse_proxy}, "
            f"ssh_mode={audit.service.ssh_mode}"
        )
