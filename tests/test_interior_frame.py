from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest

from cityg.planning.interior_frame import InteriorFrame
from cityg.planning.spatial_layout import solve_spatial_floor
from cityg.planning.interior_capability import reserve_interiors
from cityg.planning.interior_capacity_search import improve_reserved_capacity
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options, DeferredFurniture
from cityg.planning.floor_brief import geometry_summary, resolve_brief
from cityg.agents.building_floor import BuildingFloorAgent
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.schemas import Bounds2D, Point2D
from test_spatial_floor import sample_program, solve
import test_floor_brief as brief_fixtures
import test_interior_capability as capability_fixtures


class InteriorFrameTests(unittest.TestCase):
    def test_transpose_preserves_three_topologies_and_all_entry_sides(self):
        for family in ('double_loaded','residential_clusters','open_office'):
            for side in ('west','east','north','south'):
                with self.subTest(family=family,side=side):
                    frame=InteriorFrame.for_entry(side)
                    entry=Point2D(0 if frame.side(side)=='west' else 24,11)
                    local=solve(sample_program(family),entrance=entry)
                    world=solve_spatial_floor(sample_program(family),floor_id='test_floor_00',level=0,height=3.2,
                        footprint=frame.bounds(Bounds2D(0,0,24,22)),corridor_depth=3,
                        core_bounds=frame.bounds(Bounds2D(10,9.5,14,12.5)),entrance=frame.point(entry),
                        circulation_axis=frame.axis)
                    self.assertEqual([r.bounds for r in world.rooms],[frame.bounds(r.bounds) for r in local.rooms])
                    self.assertEqual([d.position for d in world.doors],[frame.point(d.position) for d in local.doors])
                    rooms={r.id:r for r in world.rooms}
                    for door in world.doors:
                        self.assertTrue(rooms[door.room_a_id].bounds.contains_point(door.position,tolerance=1e-6))
                        if door.room_b_id:
                            self.assertTrue(rooms[door.room_b_id].bounds.contains_point(door.position,tolerance=1e-6))
                        else: self.assertEqual(rooms[door.room_a_id].function,'corridor')

    def test_brief_keeps_world_geometry_and_uses_local_dimensions(self):
        old,base,spec,brief=brief_fixtures.FloorBriefTests().fixture()
        frame=InteriorFrame('y');b=deepcopy(old)
        b.footprint=frame.bounds(b.footprint);b.entrance=frame.point(b.entrance)
        b.metadata['interior_layout_contract']={'circulation_axis':'y'}
        before=deepcopy(b)
        geometry=geometry_summary(b,base)
        self.assertEqual(geometry['bands'],geometry_summary(old,base)['bands'])
        self.assertEqual(geometry['plate']['max_y'],40)
        profile=resolve_brief(brief,b,base,spec)
        BuildingFloorAgent._check_spatial_feasibility(profile,b,spec)
        self.assertEqual(b,before)

    def test_north_south_reservation_capacity_and_compiled_connectors(self):
        spec,program,_=capability_fixtures.InteriorCapabilityTests().fixture()
        runtime=GenerationPrototypes(load_options(Path(__file__).resolve().parents[1]/'configs/reliability_prototypes.json'))
        for side in ('north','south'):
            with self.subTest(side=side):
                revised=replace(program,building=replace(program.building,profiles=tuple(
                    replace(p,entrance_side=side) for p in program.building.profiles)))
                draft=ProgrammedCityPlanner(revised,floor_detail_agent=DeferredFurniture()).plan(spec)
                eligible=[b for b in draft.iter_buildings() if b.metadata['entrance_side']==side and not b.metadata['orientation_deg']]
                self.assertTrue(eligible)
                targets,pins,_=reserve_interiors(draft,limit=1,explicit_ids=[eligible[0].id],
                    room_library=runtime.floors.room_library,
                    corridor_ratios={p.function:p.corridor_ratio for p in revised.floor.profiles})
                self.assertEqual(list(targets),[eligible[0].id])
                targets,_=improve_reserved_capacity(revised,spec,targets,pins,runtime.floors.room_library,max_candidates=4)
                city=ProgrammedCityPlanner(revised,floor_detail_agent=DeferredFurniture(),
                    interior_targets=targets,archetype_pins=pins).plan(spec)
                original={b.id:b for b in draft.iter_buildings()}
                for b in city.iter_buildings():
                    if b.id not in targets:
                        for field in ('footprint','entrance','floors','vertical_connectors'):
                            self.assertEqual(getattr(b,field),getattr(original[b.id],field))
                        self.assertEqual(b.metadata['archetype_id'],original[b.id].metadata['archetype_id'])
                        continue
                    self.assertEqual(b.metadata['entrance_side'],side)
                    self.assertAlmostEqual(b.entrance.x,original[b.id].entrance.x)
                    self.assertAlmostEqual(b.entrance.y,original[b.id].entrance.y)
                    self.assertTrue(original[b.id].footprint.contains_bounds(b.footprint,tolerance=1e-6))
                    self.assertEqual(b.metadata['interior_layout_contract']['circulation_axis'],'y')
                    for f in b.floors:
                        corridors=[r for r in f.rooms if r.function=='corridor']
                        for c in b.vertical_connectors:
                            self.assertTrue(any(r.bounds.contains_bounds(c.bounds,tolerance=1e-6) for r in corridors))
                    city.metadata['interior_scope']={'building_levels':{b.id:[f.level for f in b.floors]}}
                    scene=GeometryCompiler().compile(city)
                    validation=GeometryValidator().validate(city,scene)
                    self.assertTrue(validation.ok,validation.to_dict())
                    stairs={c.id:c for c in b.vertical_connectors}
                    steps=[p for p in scene.primitives if p.semantic_class=='stair_tread']
                    self.assertTrue(steps)
                    for p in steps:
                        bounds=Bounds2D(p.center.x-p.size.x/2,p.center.y-p.size.y/2,
                                        p.center.x+p.size.x/2,p.center.y+p.size.y/2)
                        self.assertTrue(stairs[p.owner_id].bounds.contains_bounds(bounds,tolerance=1e-6))

    def test_furnished_plans_cannot_be_transposed(self):
        floor=solve(sample_program('double_loaded'))
        floor.rooms[1].object_ids.append('existing_item')
        with self.assertRaisesRegex(ValueError,'unfurnished'):
            InteriorFrame('y').floor(floor)


if __name__=='__main__': unittest.main()
