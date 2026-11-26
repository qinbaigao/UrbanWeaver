"""Run the reproducible CPU-only Gate G1 checks."""

from __future__ import annotations

import time

from cityg.evaluation import error_regression_suite, random_city_specs
from cityg.planning import BaselineCityPlanner
from cityg.serialization import to_primitive
from cityg.validation import CityValidator


def main() -> int:
    planner = BaselineCityPlanner()
    validator = CityValidator()
    started = time.perf_counter()
    generated = []
    for spec in random_city_specs():
        city = planner.plan(spec)
        report = validator.validate(city)
        if not report.ok:
            print(f"FAIL random spec {spec.name}: {report.to_dict()}")
            return 1
        generated.append(city)

    first_spec = random_city_specs(count=1)[0]
    if to_primitive(planner.plan(first_spec)) != to_primitive(planner.plan(first_spec)):
        print("FAIL deterministic replay")
        return 1

    regression_city = max(
        (
            city
            for city in generated
            if any(building.vertical_connectors for building in city.iter_buildings())
        ),
        key=lambda city: len(list(city.iter_buildings())),
    )
    regression_count = 0
    for case, expected, invalid_city in error_regression_suite(regression_city):
        regression_count += 1
        report = validator.validate(invalid_city)
        codes = {issue.code for issue in report.errors}
        if not expected.issubset(codes):
            print(f"FAIL injected case {case}: expected {sorted(expected)}, got {sorted(codes)}")
            return 1

    elapsed = time.perf_counter() - started
    print(
        f"Gate G1 checks passed: 100/100 random specs valid, "
        f"{regression_count}/{regression_count} injected regression cases localized, "
        f"deterministic replay passed ({elapsed:.2f}s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
