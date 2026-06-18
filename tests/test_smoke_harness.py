from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tooling.smoke.harness import SimulationHarness
from tooling.smoke.planner import PlanStage, build_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "smoke"


class SmokePlannerTests(unittest.TestCase):
    def test_build_plan_keeps_stage_order_and_flags_optional_checks(self) -> None:
        plan = build_plan(PlanStage.FORGEJO_10_VALIDATION)
        check_ids = [check.id for check in plan.checks]

        self.assertEqual(check_ids[0], "service-health")
        self.assertIn("ui-login-non-admin", check_ids)
        self.assertIn("attachments-load", check_ids)
        self.assertFalse(
            next(check for check in plan.checks if check.id == "attachments-load").required_for_stage(
                plan.stage
            )
        )

    def test_required_only_plan_excludes_optional_checks(self) -> None:
        plan = build_plan(PlanStage.FORGEJO_10_VALIDATION, include_optional=False)
        check_ids = [check.id for check in plan.checks]

        self.assertNotIn("service-health", check_ids)
        self.assertNotIn("attachments-load", check_ids)
        self.assertIn("ui-login-admin", check_ids)


class SimulationHarnessTests(unittest.TestCase):
    def test_success_fixture_reports_ok(self) -> None:
        plan = build_plan(PlanStage.POST_CUTOVER)
        harness = SimulationHarness.from_path(FIXTURE_DIR / "post_cutover_success.json")

        report = harness.run(plan)

        self.assertTrue(report.summary.ok)
        self.assertEqual(report.summary.failed, 0)
        self.assertEqual(report.summary.skipped, 0)
        self.assertEqual(report.summary.total, len(plan.checks))

    def test_failed_dependency_marks_dependents_skipped(self) -> None:
        plan = build_plan(PlanStage.POST_CUTOVER)
        harness = SimulationHarness.from_path(FIXTURE_DIR / "post_cutover_failure.json")

        report = harness.run(plan)
        by_id = {result.id: result for result in report.results}

        self.assertFalse(report.summary.ok)
        self.assertEqual(by_id["ssh-clone-private-repo"].status, "failed")
        self.assertEqual(by_id["push-test-disposable-repo"].status, "skipped")
        self.assertEqual(by_id["webhook-delivery"].status, "skipped")
        self.assertGreaterEqual(report.summary.required_failures, 2)

    def test_fixture_stage_mismatch_is_rejected(self) -> None:
        plan = build_plan(PlanStage.POST_CUTOVER)
        harness = SimulationHarness.from_path(FIXTURE_DIR / "forgejo_10_success.json")

        with self.assertRaisesRegex(ValueError, "does not match plan stage"):
            harness.run(plan)


class SmokeCliTests(unittest.TestCase):
    def test_cli_plan_outputs_json(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tooling.smoke.cli",
                "plan",
                "--stage",
                PlanStage.POST_CUTOVER.value,
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["stage"], PlanStage.POST_CUTOVER.value)
        self.assertGreater(len(payload["checks"]), 0)

    def test_cli_run_fails_on_unsuccessful_fixture(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tooling.smoke.cli",
                "run",
                "--stage",
                PlanStage.POST_CUTOVER.value,
                "--fixture",
                str(FIXTURE_DIR / "post_cutover_failure.json"),
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(payload["summary"]["ok"])


if __name__ == "__main__":
    unittest.main()
