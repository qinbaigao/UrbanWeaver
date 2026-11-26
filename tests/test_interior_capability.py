import json
import unittest
from copy import deepcopy

from cityg.planning.interior_capability import reserve_interiors
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.programs import HierarchicalProgram, UrbanProgram, BuildingProgram, FloorProgram, SkylineProgram
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.prototype_adaptation import door_side
from cityg.geometry import GeometryCompiler
from cityg.schemas import CitySpec
from cityg.validation import CityValidator
from test_generation_prototypes import offline_responses
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options


class InteriorCapabilityTests(unittest.TestCase):
    def test_bounded_capacity_search_preserves_semantics_and_non_targets(self):
        from pathlib import Path
        from cityg.planning.interior_capacity_search import improve_reserved_capacity
        spec, program, draft = self.fixture()
        runtime = GenerationPrototypes(load_options(Path(__file__).resolve().parents[1]/'configs/generation_prototypes.json'))
        targets, pins, _ = reserve_interiors(draft, limit=2, room_library=runtime.floors.room_library)
        before_targets = deepcopy(targets)
        selected, report = improve_reserved_capacity(program, spec, targets, pins,
            runtime.floors.room_library, max_candidates=8)
        self.assertEqual(targets, before_targets)
        for row in report['buildings']:
            self.assertGreaterEqual(row['after_compatible_rooms'], row['before_compatible_rooms'])
            self.assertLessEqual(len(row['candidates']), 8)
        old = ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture(),
            interior_targets=targets, archetype_pins=pins).plan(spec)
        new = ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture(),
            interior_targets=selected, archetype_pins=pins).plan(spec)
        for a, b in zip(old.iter_buildings(), new.iter_buildings()):
            self.assertEqual(a.function, b.function)
            if a.id not in selected: self.assertEqual(a, b)
        self.assertFalse(any(new.iter_objects()))

    def fixture(self):
        responses = offline_responses()
        spec = CitySpec.from_dict(json.loads(responses[1]))
        urban, skyline, building, spaces, floor = [json.loads(r['program_json']) for r in responses[2:]]
        program = HierarchicalProgram(UrbanProgram.from_dict(urban), BuildingProgram.from_dict(building),
                                      FloorProgram.from_dict(floor), SkylineProgram.from_dict(skyline))
        draft = ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture()).plan(spec)
        return spec, program, draft

    def test_scope_preserves_other_buildings_and_uses_exact_plate(self):
        spec, program, draft = self.fixture(); before = deepcopy(draft)
        targets, pins, report = reserve_interiors(draft, limit=3)
        self.assertTrue(targets)
        self.assertLessEqual(len(targets), 3)
        self.assertEqual(draft, before)
        city = ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture(),
                    interior_targets=targets, archetype_pins=pins).plan(spec)
        self.assertTrue(CityValidator().validate(city).ok)
        old = {b.id: b for b in draft.iter_buildings()}
        for b in city.iter_buildings():
            self.assertEqual(b.footprint, old[b.id].footprint)
            if b.id not in targets:
                self.assertEqual(b.floors, old[b.id].floors)
                self.assertEqual(b.metadata['archetype_id'], old[b.id].metadata['archetype_id'])
                continue
            frame = GeometryCompiler._massing_frame(b)
            self.assertAlmostEqual(frame['max_x']-frame['min_x'], b.footprint.width)
            self.assertAlmostEqual(frame['max_y']-frame['min_y'], b.footprint.depth)
            f = b.floors[0]; door = next(d for d in f.doors if d.room_b_id is None)
            room = next(r for r in f.rooms if r.id == door.room_a_id)
            env = metric_envelope(b, f, room)
            self.assertEqual(env['status'], 'supported')
            self.assertEqual(door_side(env['room'], next(d for d in env['floor'].doors if d.id == door.id)),
                             targets[b.id]['entrance_side'])

    def test_explicit_unsupported_target_never_changes_identity(self):
        _, _, city = self.fixture(); b = next(city.iter_buildings())
        b.metadata['orientation_deg'] = 17
        targets, _, report = reserve_interiors(city, limit=3, explicit_ids=[b.id])
        self.assertFalse(targets)
        self.assertIn(b.id, [r['building_id'] for r in report['rejected']])
        with self.assertRaises(ValueError): reserve_interiors(city, limit=3, explicit_ids=['missing'])

    def test_capacity_reservation_is_new_layout_not_furniture_scaling(self):
        from pathlib import Path
        spec, program, draft = self.fixture()
        runtime = GenerationPrototypes(load_options(Path(__file__).resolve().parents[1]/'configs/generation_prototypes.json'))
        ratios = {p.function: p.corridor_ratio for p in program.floor.profiles}
        targets, pins, _ = reserve_interiors(draft, limit=3, room_library=runtime.floors.room_library,
                                           corridor_ratios=ratios)
        city = ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture(),
                    interior_targets=targets, archetype_pins=pins).plan(spec)
        old = {b.id:b for b in draft.iter_buildings()}
        for b in city.iter_buildings():
            if b.id in targets:
                self.assertTrue(old[b.id].footprint.contains_bounds(b.footprint))
                self.assertTrue(targets[b.id].get('dimension_reference_ids'))
                contract = targets[b.id]
                if b.footprint.depth < old[b.id].footprint.depth-1e-6:
                    corridor = ProgrammedCityPlanner._corridor_depth(b.footprint.depth, ratios[b.function])
                    self.assertAlmostEqual((b.footprint.depth-corridor)/2, contract['reference_band_depth_m'])
            else:
                self.assertEqual(b.footprint, old[b.id].footprint)
        self.assertFalse(list(city.iter_objects()))
        self.assertTrue(CityValidator().validate(city).ok)

    def test_conflicting_massing_contract_fails_closed(self):
        _, _, city = self.fixture(); b = next(city.iter_buildings())
        b.metadata['interior_layout_contract'] = {'source': 'new_scene_rectangular_interior_v1'}
        b.metadata['massing_style'] = 'l_shape'
        with self.assertRaisesRegex(ValueError, 'conflicts with massing'):
            GeometryCompiler._massing_parts(b)


if __name__ == '__main__': unittest.main()
