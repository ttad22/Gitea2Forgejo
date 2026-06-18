from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .planner import CHECK_INDEX, PlanStage, SmokeCheck, SmokePlan, build_plan, validate_check_ids


@dataclass(frozen=True)
class CheckResult:
    id: str
    title: str
    status: str
    required: bool
    detail: str
    stage: str
    depends_on: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "required": self.required,
            "detail": self.detail,
            "stage": self.stage,
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class RunSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    required_failures: int
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "required_failures": self.required_failures,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class SmokeRunReport:
    fixture_name: str
    plan: SmokePlan
    summary: RunSummary
    results: tuple[CheckResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_name": self.fixture_name,
            "plan": self.plan.to_dict(),
            "summary": self.summary.to_dict(),
            "results": [result.to_dict() for result in self.results],
        }


class SimulationHarness:
    """Execute a smoke plan against a local fixture describing expected outcomes."""

    def __init__(self, fixture: dict[str, Any]) -> None:
        self.fixture = fixture
        self.fixture_name = fixture.get("name", "unnamed-fixture")

    @classmethod
    def from_path(cls, path: str | Path) -> "SimulationHarness":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    def validate_fixture(self, plan: SmokePlan | None = None) -> list[str]:
        fixture_stage = self.fixture.get("stage")
        errors: list[str] = []
        if fixture_stage is None:
            errors.append("Fixture is missing 'stage'.")
        else:
            try:
                PlanStage(fixture_stage)
            except ValueError:
                errors.append(f"Unsupported fixture stage: {fixture_stage}")

        outcomes = self.fixture.get("outcomes")
        if not isinstance(outcomes, dict):
            errors.append("Fixture is missing an 'outcomes' object.")
        else:
            unknown = validate_check_ids(outcomes.keys())
            if unknown:
                errors.append(f"Fixture references unknown checks: {', '.join(sorted(unknown))}")

        if plan is not None and fixture_stage is not None and fixture_stage != plan.stage.value:
            errors.append(
                f"Fixture stage '{fixture_stage}' does not match plan stage '{plan.stage.value}'."
            )

        return errors

    def run(self, plan: SmokePlan, strict: bool = True) -> SmokeRunReport:
        errors = self.validate_fixture(plan)
        if errors:
            raise ValueError("; ".join(errors))

        outcomes = self.fixture["outcomes"]
        results: list[CheckResult] = []
        status_by_id: dict[str, str] = {}

        for check in plan.checks:
            dependency_failure = self._first_blocking_dependency(check, status_by_id)
            if dependency_failure:
                result = CheckResult(
                    id=check.id,
                    title=check.title,
                    status="skipped",
                    required=check.required_for_stage(plan.stage),
                    detail=f"Skipped because dependency '{dependency_failure}' did not pass.",
                    stage=plan.stage.value,
                    depends_on=check.depends_on,
                )
            else:
                outcome = outcomes.get(check.id)
                if outcome is None:
                    if strict:
                        raise ValueError(f"Fixture '{self.fixture_name}' is missing outcome for '{check.id}'.")
                    status = "passed"
                    detail = "No explicit fixture outcome. Defaulted to pass."
                else:
                    status = outcome.get("status", "passed")
                    detail = outcome.get("detail", "")
                result = CheckResult(
                    id=check.id,
                    title=check.title,
                    status=status,
                    required=check.required_for_stage(plan.stage),
                    detail=detail,
                    stage=plan.stage.value,
                    depends_on=check.depends_on,
                )

            status_by_id[result.id] = result.status
            results.append(result)

        summary = self._build_summary(results)
        return SmokeRunReport(
            fixture_name=self.fixture_name,
            plan=plan,
            summary=summary,
            results=tuple(results),
        )

    @staticmethod
    def _first_blocking_dependency(check: SmokeCheck, status_by_id: dict[str, str]) -> str | None:
        for dependency_id in check.depends_on:
            if status_by_id.get(dependency_id) != "passed":
                return dependency_id
        return None

    @staticmethod
    def _build_summary(results: list[CheckResult]) -> RunSummary:
        passed = sum(1 for result in results if result.status == "passed")
        failed = sum(1 for result in results if result.status == "failed")
        skipped = sum(1 for result in results if result.status == "skipped")
        required_failures = sum(
            1 for result in results if result.required and result.status in {"failed", "skipped"}
        )
        return RunSummary(
            total=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            required_failures=required_failures,
            ok=required_failures == 0,
        )


def run_fixture(path: str | Path, stage: PlanStage | str, include_optional: bool = True) -> SmokeRunReport:
    plan = build_plan(stage=stage, include_optional=include_optional)
    harness = SimulationHarness.from_path(path)
    return harness.run(plan)
