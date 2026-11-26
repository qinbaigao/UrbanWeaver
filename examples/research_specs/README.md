# City specification examples

These ten fixed-seed examples exercise the deterministic planner from low-rise residential neighbourhoods to dense mixed-use districts. Each JSON file must parse with `CitySpec.from_dict`, produce the requested building count, pass the structural validators and replay exactly with the same seed.

Run the complete set from the repository root:

```bash
PYTHONPATH=src python scripts/validate_research_specs.py
```

`10_scalability_stress.json` measures CPU semantic planning. Full multi-agent generation, physics simulation and high-fidelity rendering incur additional costs and need separate benchmarks.

A spec with no layout parameters uses the reproducible `organic_grid` default. For a 40-building visual example, see [the mixed district](../mixed_district.json). For a regular layout with one building per block, set `layout_style` to `regular_grid`, `road_pattern` to `connected_grid` and `buildings_per_block` to `1`.
