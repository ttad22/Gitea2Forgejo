from __future__ import annotations

import json

from gitea_forgejo_migrator.cli import main

from .test_audit import build_report


def test_cli_audit_json_output(tmp_path, capsys) -> None:
    report_path = tmp_path / "audit.json"
    report_path.write_text(json.dumps(build_report().to_dict()), encoding="utf-8")

    exit_code = main(["audit", str(report_path), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["audit"]["ready"] is True
    assert payload["report"]["host_label"] == "vm100"


def test_cli_gate_fails_for_direct_current_target(tmp_path, capsys) -> None:
    report_path = tmp_path / "audit.json"
    report_path.write_text(json.dumps(build_report().to_dict()), encoding="utf-8")

    exit_code = main(["gate", str(report_path), "--target", "forgejo-current"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "allowed: no" in captured.out
    assert "Forgejo 10" in captured.out
