"""Deterministic research evaluation helpers."""

from cityg.evaluation.error_injection import (
    ERROR_CASES,
    ERROR_VARIANTS_PER_CASE,
    error_regression_suite,
    inject_error,
)
from cityg.evaluation.random_specs import random_city_specs

__all__ = [
    "ERROR_CASES",
    "ERROR_VARIANTS_PER_CASE",
    "error_regression_suite",
    "inject_error",
    "random_city_specs",
]
