"""Trusted executor requirements for choosing a minimal *capable* repair scope.

These are capability/dependency declarations, not model claims of feasibility.
Unknown requirements retain the old search; all selected candidates still pass
the transaction, geometry and independent task-resolution gates.
"""
from dataclasses import dataclass

from cityg.ccwp import entity_index
from cityg.transactions import descendants


@dataclass(frozen=True)
class ScopeRequirements:
    required_entity_ids: tuple[str, ...]
    capable_scope_types: tuple[str, ...] = ('room', 'floor', 'building')
    unsupported_reason: str | None = None

    def validate(self, city):
        if not self.required_entity_ids or set(self.required_entity_ids) - entity_index(city).keys():
            raise ValueError('Scope dependencies must name existing entities')
        if not self.capable_scope_types or set(self.capable_scope_types) - {'room', 'floor', 'building'}:
            raise ValueError('Invalid executor scope capabilities')
        if self.unsupported_reason is not None and not self.unsupported_reason.strip():
            raise ValueError('An unsupported capability needs an explicit reason')

    def exclusion(self, city, kind, scope_id):
        if kind not in self.capable_scope_types:
            return 'executor_scope_incapable'
        if set(self.required_entity_ids) - descendants(city, [scope_id]):
            return 'incomplete_dependency_coverage'
        return None
