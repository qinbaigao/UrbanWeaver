"""Lightweight runtime checks shared by future simulator adapters."""

from cityg.runtime.activation import ActivationManager
from cityg.runtime.interaction import InteractionRuntime, run_interaction_smoke
from cityg.runtime.navigation import NavigationQuery

__all__ = [
    "ActivationManager",
    "InteractionRuntime",
    "NavigationQuery",
    "run_interaction_smoke",
]
