import tempfile
import unittest
from pathlib import Path

from cityg.memory import MemoryQuery, MemoryRecord, MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_scope_version_status_and_context_disclosure(self):
        with tempfile.TemporaryDirectory() as temporary:
            with MemoryStore(Path(temporary) / "memory.sqlite3") as store:
                store.put(MemoryRecord(
                    "m1", "building_refinement", "building", "building_000",
                    {"massing": "setback"}, world_version=1,
                    tags=("commercial", "corner"), producer="test",
                    validation_status="accepted", run_id="run_a",
                ))
                store.put(MemoryRecord(
                    "m2", "building_refinement", "building", "building_000",
                    {"massing": "offset"}, world_version=2,
                    tags=("commercial",), producer="test",
                    validation_status="candidate", run_id="run_a",
                ))
                result = store.query(MemoryQuery(
                    scope_id="building_000", world_version=1, run_id="run_a",
                    tags=("commercial",),
                ))
                self.assertEqual([item.memory_id for item in result], ["m1"])
                section = store.context_section(
                    "accepted", "accepted refinements",
                    MemoryQuery(scope_id="building_000", world_version=1, run_id="run_a"),
                )
                self.assertEqual(section.value[0]["memory_id"], "m1")
                self.assertEqual(
                    store.invalidate_scope(
                        "building_000", current_world_version=2, reason="world_patch"
                    ),
                    1,
                )
                self.assertEqual(store.get("m1").validation_status, "stale")

    def test_cross_run_memory_is_opt_in(self):
        with tempfile.TemporaryDirectory() as temporary:
            with MemoryStore(Path(temporary) / "memory.sqlite3") as store:
                store.put(MemoryRecord(
                    "shared", "semantic_pattern", "city", "global",
                    {"rule": "align core facades"}, validation_status="accepted",
                    cross_run=True,
                ))
                self.assertEqual(store.query(MemoryQuery()), [])
                self.assertEqual(
                    [item.memory_id for item in store.query(MemoryQuery(allow_cross_run=True))],
                    ["shared"],
                )


if __name__ == "__main__":
    unittest.main()
