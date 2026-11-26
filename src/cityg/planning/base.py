"""Planner contracts."""

from typing import Protocol

from cityg.schemas import City, CitySpec


class CityPlanner(Protocol):
    """Convert a validated city specification into the canonical world model."""

    def plan(self, spec: CitySpec) -> City:
        ...

