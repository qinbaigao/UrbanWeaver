from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    entity_id: str | None = None
    constraint_id: str | None = None
    violating_entities: tuple[str, ...] = ()
    responsible_ancestor: str | None = None
    dependency_path: tuple[str, ...] = ()
    observed_value: Any = None
    required_value: Any = None
    allowed_patch_scope: str | None = None
    suggested_operations: tuple[str, ...] = ()


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def counterexamples(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.constraint_id is not None]

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        entity_id: str | None = None,
        *,
        constraint_id: str | None = None,
        violating_entities: tuple[str, ...] = (),
        responsible_ancestor: str | None = None,
        dependency_path: tuple[str, ...] = (),
        observed_value=None,
        required_value=None,
        allowed_patch_scope: str | None = None,
        suggested_operations: tuple[str, ...] = (),
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                message=message,
                entity_id=entity_id,
                constraint_id=constraint_id,
                violating_entities=violating_entities,
                responsible_ancestor=responsible_ancestor,
                dependency_path=dependency_path,
                observed_value=observed_value,
                required_value=required_value,
                allowed_patch_scope=allowed_patch_scope,
                suggested_operations=suggested_operations,
            )
        )

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "counterexample_count": len(self.counterexamples),
            "metrics": self.metrics,
            "issues": [asdict(issue) for issue in self.issues],
        }
