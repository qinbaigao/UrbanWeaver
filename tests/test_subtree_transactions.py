import unittest
from copy import deepcopy
from unittest.mock import patch

from cityg.ccwp import build_world_program, entity_index
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.subtree_transactions import (
    BuildingSubtreePlanner,
    FloorSubtreePlanner,
    UrbanSubgraphPlanner,
)
from cityg.subtree_transactions import _details_spec


def make_city():
    city = BaselineCityPlanner().plan(
        CitySpec(width_m=220, depth_m=220, building_count=3,
                 min_floors=2, max_floors=4, rooms_per_floor=4, seed=7)
    )
    city.world_program = build_world_program(city, producer="test", seed=7)
    return city


class SubtreeTransactionTests(unittest.TestCase):
    def test_building_floor_count_is_never_silently_clamped_or_truncated(self):
        city = make_city()
        building = next(city.iter_buildings())
        original = deepcopy(city)
        for count in (0, -1, 129, 10000, 2.5, True, 'nonsense'):
            with self.subTest(count=count):
                with patch.object(FloorSubtreePlanner, 'replace',
                                  side_effect=AssertionError('invalid counts must fail before realization')):
                    with self.assertRaisesRegex(ValueError, 'floor_count'):
                        BuildingSubtreePlanner().replace(city, building.id, {'floor_count': count})
                self.assertEqual(city, original)

    def test_building_stack_with_different_floor_heights_stays_contiguous(self):
        city = make_city()
        building = next(city.iter_buildings())
        building.floors[0].height_m = 4.5
        elevation = 0.0
        for floor in building.floors:
            floor.elevation_m = elevation
            elevation += floor.height_m
        result = BuildingSubtreePlanner().replace(
            city, building.id, {'floor_count': len(building.floors) + 1, 'room_count': 4})
        edited = next(b for b in result.city.iter_buildings() if b.id == building.id)
        elevation = building.floors[0].elevation_m
        for floor in edited.floors:
            self.assertAlmostEqual(floor.elevation_m, elevation)
            elevation += floor.height_m

    def test_natural_language_room_and_floor_counts_are_parsed(self):
        self.assertEqual(_details_spec("重新规划为14个房间")['room_count'], 14)
        self.assertEqual(_details_spec("set exactly 18 floors")['floor_count'], 18)
        self.assertEqual(
            _details_spec("Change district function to mixed residential and public service.")['function'],
            "mixed_use_residential_public_service",
        )
    def test_floor_replacement_is_atomic_and_rebuilds_doors(self):
        city = make_city()
        building = next(city.iter_buildings())
        floor = building.floors[0]
        old_json = [(room.id, room.function) for room in floor.rooms]
        result = FloorSubtreePlanner().replace(city, floor.id, {"room_count": 10})
        self.assertEqual(old_json, [(room.id, room.function) for room in floor.rooms])
        edited_floor = next(item for item in result.city.iter_floors() if item.id == floor.id)
        self.assertEqual(len([r for r in edited_floor.rooms if r.function != "corridor"]), 10)
        room_ids = {room.id for room in edited_floor.rooms}
        self.assertTrue(all(door.room_a_id in room_ids for door in edited_floor.doors))
        self.assertTrue(result.validation.ok)
        self.assertEqual(len(city.world_program.nodes), len(entity_index(city)))

    def test_building_replacement_changes_floor_stack_without_orphans(self):
        city = make_city()
        building = next(city.iter_buildings())
        result = BuildingSubtreePlanner().replace(
            city, building.id, {"floor_count": len(building.floors) + 1, "room_count": 6}
        )
        edited = next(item for item in result.city.iter_buildings() if item.id == building.id)
        self.assertEqual(len(edited.floors), len(building.floors) + 1)
        all_rooms = {room.id for floor in edited.floors for room in floor.rooms}
        self.assertTrue(all(door.room_a_id in all_rooms or door.room_a_id.startswith(edited.id)
                            for floor in edited.floors for door in floor.doors))
        self.assertTrue(result.validation.ok)

    def test_urban_subgraph_does_not_touch_other_districts(self):
        city = make_city()
        districts = list(city.districts)
        original = {item.id: item.function for item in districts}
        result = UrbanSubgraphPlanner().replace(city, districts[0].id, {"function": "public_service"})
        edited = {item.id: item.function for item in result.city.districts}
        self.assertEqual(edited[districts[0].id], "public_service")
        for district in districts[1:]:
            self.assertEqual(edited[district.id], original[district.id])
        self.assertTrue(result.validation.ok)


if __name__ == "__main__":
    unittest.main()
