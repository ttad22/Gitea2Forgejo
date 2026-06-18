"""Core package for deployment audit and compatibility gating."""

from .audit import AuditFinding, AuditOutcome, evaluate_deployment
from .compatibility import CompatibilityDecision, evaluate_compatibility
from .models import DeploymentAuditReport

__all__ = [
    "AuditFinding",
    "AuditOutcome",
    "CompatibilityDecision",
    "DeploymentAuditReport",
    "evaluate_compatibility",
    "evaluate_deployment",
]
