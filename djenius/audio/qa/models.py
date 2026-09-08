"""Data models for the QA gate provenance system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QAViolation:
    """A single objective QA failure with full provenance."""

    module: str
    metric: str
    threshold: float
    observed: float
    timestamp: float | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "metric": self.metric,
            "threshold": self.threshold,
            "observed": self.observed,
            "timestamp": self.timestamp,
            "context": dict(self.context),
        }


@dataclass
class QAResult:
    """Aggregate result of the QA gate evaluation."""

    passed: bool = True
    violations: list[QAViolation] = field(default_factory=list)

    def add(self, violation: QAViolation) -> None:
        self.violations.append(violation)
        self.passed = False

    def merge(self, other: QAResult) -> None:
        self.violations.extend(other.violations)
        if not other.passed:
            self.passed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
        }
