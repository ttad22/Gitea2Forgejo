from __future__ import annotations

import pytest

from gitea_forgejo_migrator.adapters import PlatformAdapterRegistry, SystemdBinaryAdapter

from .test_executor import _audit


def test_registry_resolves_supported_systemd_cohort() -> None:
    adapter = PlatformAdapterRegistry().resolve(_audit())
    assert isinstance(adapter, SystemdBinaryAdapter)
    assert adapter.adapter_name == "systemd-binary-postgresql-nginx-host-sshd"


def test_registry_rejects_unsupported_cohort() -> None:
    audit = _audit()
    audit.service.database = "sqlite"

    with pytest.raises(RuntimeError) as excinfo:
        PlatformAdapterRegistry().resolve(audit)

    assert "unsupported deployment cohort" in str(excinfo.value)
