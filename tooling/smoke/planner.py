from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Iterable


class PlanStage(str, Enum):
    FORGEJO_10_VALIDATION = "forgejo_10_validation"
    POST_CUTOVER = "post_cutover"


@dataclass(frozen=True)
class SmokeCheck:
    id: str
    title: str
    description: str
    required: bool = True
    stage_overrides: dict[PlanStage, dict[str, bool]] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def required_for_stage(self, stage: PlanStage) -> bool:
        override = self.stage_overrides.get(stage, {})
        return override.get("required", self.required)

    def to_dict(self, stage: PlanStage) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = stage.value
        payload["required"] = self.required_for_stage(stage)
        return payload


@dataclass(frozen=True)
class SmokePlan:
    stage: PlanStage
    checks: tuple[SmokeCheck, ...]
    include_optional: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "include_optional": self.include_optional,
            "checks": [check.to_dict(self.stage) for check in self.checks],
        }


CHECKS: tuple[SmokeCheck, ...] = (
    SmokeCheck(
        id="service-health",
        title="Service health",
        description="Verify Forgejo, nginx, and PostgreSQL are active and serving requests.",
        stage_overrides={PlanStage.FORGEJO_10_VALIDATION: {"required": False}},
        tags=("system", "health"),
    ),
    SmokeCheck(
        id="web-health-endpoint",
        title="Web health endpoint",
        description="Check that the web health endpoint returns a healthy response.",
        depends_on=("service-health",),
        stage_overrides={PlanStage.FORGEJO_10_VALIDATION: {"required": False}},
        tags=("system", "http"),
    ),
    SmokeCheck(
        id="ui-login-admin",
        title="UI login as admin",
        description="Sign in with an administrator account and verify the dashboard loads.",
        depends_on=("web-health-endpoint",),
        tags=("ui", "auth", "admin"),
    ),
    SmokeCheck(
        id="ui-login-non-admin",
        title="UI login as non-admin",
        description="Sign in with a non-admin account and verify a normal user session works.",
        depends_on=("web-health-endpoint",),
        stage_overrides={PlanStage.FORGEJO_10_VALIDATION: {"required": False}},
        tags=("ui", "auth", "user"),
    ),
    SmokeCheck(
        id="repo-browse",
        title="Repository browse",
        description="Open a representative repository and verify tree browsing succeeds.",
        depends_on=("ui-login-admin",),
        tags=("ui", "repo"),
    ),
    SmokeCheck(
        id="issue-view",
        title="Issue view",
        description="Open an existing issue and confirm metadata and comments render.",
        depends_on=("repo-browse",),
        tags=("ui", "issues"),
    ),
    SmokeCheck(
        id="pr-view",
        title="Pull request view",
        description="Open an existing pull request and confirm discussion and diff render.",
        depends_on=("repo-browse",),
        tags=("ui", "pull-request"),
    ),
    SmokeCheck(
        id="http-clone-private-repo",
        title="HTTPS clone of a private repo",
        description="Clone a private repository over HTTP(S) using standard credentials.",
        depends_on=("ui-login-admin",),
        tags=("git", "http", "private-repo"),
    ),
    SmokeCheck(
        id="ssh-clone-private-repo",
        title="SSH clone of a private repo",
        description="Clone a private repository over SSH using an authorized key.",
        depends_on=("ui-login-admin",),
        tags=("git", "ssh", "private-repo"),
    ),
    SmokeCheck(
        id="push-test-disposable-repo",
        title="Push test to disposable repo",
        description="Create a branch or disposable repository and push a validation commit.",
        depends_on=("http-clone-private-repo", "ssh-clone-private-repo"),
        tags=("git", "push"),
    ),
    SmokeCheck(
        id="webhook-list",
        title="Webhook list",
        description="Load configured webhooks and verify delivery metadata is visible.",
        depends_on=("repo-browse",),
        tags=("integrations", "webhook"),
    ),
    SmokeCheck(
        id="webhook-delivery",
        title="Webhook delivery",
        description="Trigger or inspect a webhook delivery to confirm dispatch still works.",
        depends_on=("webhook-list", "push-test-disposable-repo"),
        stage_overrides={PlanStage.FORGEJO_10_VALIDATION: {"required": False}},
        tags=("integrations", "webhook"),
    ),
    SmokeCheck(
        id="attachments-load",
        title="Attachments load",
        description="Open an attachment-backed issue or release asset and verify the payload downloads.",
        depends_on=("ui-login-admin",),
        stage_overrides={PlanStage.FORGEJO_10_VALIDATION: {"required": False}},
        tags=("artifacts", "attachments"),
    ),
    SmokeCheck(
        id="repo-archive-download",
        title="Repository archive download",
        description="Download a source archive and verify the generated artifact is valid.",
        depends_on=("repo-browse",),
        stage_overrides={PlanStage.FORGEJO_10_VALIDATION: {"required": False}},
        tags=("artifacts", "archives"),
    ),
    SmokeCheck(
        id="lfs-endpoint-sanity",
        title="LFS endpoint sanity",
        description="Check that the Git LFS endpoint responds correctly even if LFS is unused.",
        depends_on=("web-health-endpoint",),
        tags=("git", "lfs"),
    ),
)

CHECK_INDEX = {check.id: check for check in CHECKS}


def build_plan(stage: PlanStage | str, include_optional: bool = True) -> SmokePlan:
    normalized_stage = PlanStage(stage)
    selected = []
    for check in CHECKS:
        if check.required_for_stage(normalized_stage):
            selected.append(check)
            continue
        if include_optional:
            selected.append(check)
    return SmokePlan(
        stage=normalized_stage,
        checks=tuple(selected),
        include_optional=include_optional,
    )


def validate_check_ids(check_ids: Iterable[str]) -> list[str]:
    unknown = [check_id for check_id in check_ids if check_id not in CHECK_INDEX]
    return unknown
