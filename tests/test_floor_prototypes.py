from copy import deepcopy
from pathlib import Path
import json
import shutil
from tempfile import TemporaryDirectory
import unittest

from cityg.planning.floor_prototypes import FloorPrototypeLibrary, circulation_raster
from cityg.planning.floor_prototype_lab import make_floor_lab, compiled_floor_checks, furnish_reference
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.validation import CityValidator


ROOT=Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1'


class FloorPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.library=FloorPrototypeLibrary(ROOT)

    def test_fourteen_references_and_room_hints_exist(self):
        self.assertEqual(len(self.library.floors),14)
        for r in self.library.floors.values():
            self.assertEqual(r['review']['status'],'pending_review')
            self.assertTrue(self.library.validate(r)['ok'])
            self.assertTrue(circulation_raster(r)['ok'])

    def test_unit_privacy_cannot_be_bypassed(self):
        r=deepcopy(self.library.floors['residential_spine_v1'])
        # A bedroom ID cannot masquerade as the unit's public root.
        r['units'][0]['entry_space']=r['units'][0]['id']+'_bed_a'
        with self.assertRaisesRegex(ValueError,'bypasses'):self.library.validate(r)

    def test_duplicate_ids_across_library_shards_rejected(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/'library';shutil.copytree(ROOT,root)
            record=self.library.floors['office_mixed_v1']
            (root/'floors_duplicate.json').write_text(json.dumps({'schema_version':1,'prototypes':[record]}))
            with self.assertRaisesRegex(ValueError,'duplicate floor'):FloorPrototypeLibrary(root)

    def test_overlap_and_incomplete_coverage_rejected(self):
        for delta in (-.5,.5):
            r=deepcopy(self.library.floors['office_mixed_v1']);r['spaces'][1]['bounds_m'][0]+=delta
            with self.assertRaises(ValueError):self.library.validate(r)

    def test_bad_doors_disconnected_graph_and_cores_rejected(self):
        for mutate in (lambda r:r['connections'].pop(),
                       lambda r:r['connections'][0].update(fraction=.01),
                       lambda r:r['connections'][0].update(b='wc'),
                       lambda r:r['cores'][0].update(bounds_m=[0,0,3,5]),
                       lambda r:r['cores'][1].update(stack_key='stair_a')):
            r=deepcopy(self.library.floors['office_mixed_v1']);mutate(r)
            with self.assertRaises(ValueError):self.library.validate(r)

    def test_open_boundary_must_match_public_connection(self):
        r=deepcopy(self.library.floors['residential_core_v1'])
        r['open_boundaries']=[]
        with self.assertRaisesRegex(ValueError,'mismatch'):self.library.validate(r)

    def test_raster_sees_barrier_beyond_door_graph(self):
        from cityg.schemas import Bounds2D
        r=self.library.floors['office_mixed_v1']
        self.assertFalse(circulation_raster(r,[Bounds2D(0,15.5,36,16.5)])['ok'])

    def test_room_dependency_changes_floor_fingerprint(self):
        lib=FloorPrototypeLibrary(ROOT);key='office_mixed_v1';before=lib.content_fingerprint(key)
        lib.room_library.rooms['office_private_v1']['intent']+=' test'
        self.assertNotEqual(before,lib.content_fingerprint(key))

    def test_new_dining_preview_keeps_tables_and_chairs_together(self):
        r=self.library.floors['food_court_v1'];objects,_=furnish_reference(r)
        space=next(s['id'] for s in r['spaces'] if s['function']=='food_court')
        tables=[o for o in objects if o['space']==space and o['category']=='dining_table']
        chairs=[o for o in objects if o['space']==space and o['category']=='dining_chair']
        self.assertGreater(len(tables),0);self.assertEqual(len(chairs),len(tables)*2)
        for table in tables:
            self.assertEqual(sum(abs(c['x']-table['x'])<1e-6 and abs(abs(c['y']-table['y'])-1.1)<1e-6 for c in chairs),2)

    def test_real_compiler_all_fixtures_and_vertical_stacks(self):
        city,rows=make_floor_lab(self.library,list(self.library.floors))
        city.world_program=build_world_program(city,producer='test',seed=17)
        semantic=CityValidator().validate(city)
        self.assertTrue(semantic.ok,semantic.to_dict())
        scene=GeometryCompiler().compile(city)
        report=GeometryValidator().validate(city,scene)
        self.assertTrue(report.ok,report.to_dict())
        self.assertTrue(all(c['ok'] for c in compiled_floor_checks(city,scene)))
        self.assertTrue(all(r['circulation_check']['ok'] for r in rows))
        self.assertTrue(any(p.semantic_class=='open_passage' for p in scene.primitives))
        for b in city.iter_buildings():
            self.assertEqual(len(b.floors),2)
            self.assertEqual([r.bounds for r in b.floors[0].rooms],[r.bounds for r in b.floors[1].rooms])
            for room in b.floors[0].rooms:
                if room.function=='bedroom':
                    self.assertTrue(any(o.room_id==room.id and o.category=='bed' for o in b.floors[0].objects))
        for district in city.districts:
            for p in district.parcels:self.assertTrue(p.bounds.contains_bounds(p.buildings[0].footprint))

    def test_open_boundary_compiler_rejects_interactive_door(self):
        city,_=make_floor_lab(self.library,['residential_core_v1'])
        f=next(city.iter_buildings()).floors[0]
        next(d for d in f.doors if d.door_type=='open_passage').interactive=True
        with self.assertRaisesRegex(ValueError,'noninteractive'):GeometryCompiler().compile(city)

    def test_reliability_floor_references_compile_and_connect(self):
        city,rows=make_floor_lab(self.library,['office_short_wing_v1','office_linear_studios_v1'])
        city.world_program=build_world_program(city,producer='test',seed=17)
        scene=GeometryCompiler().compile(city)
        self.assertTrue(GeometryValidator().validate(city,scene).ok)
        self.assertTrue(all(c['ok'] for c in compiled_floor_checks(city,scene)))
        self.assertTrue(all(r['circulation_check']['ok'] for r in rows))


if __name__=='__main__':unittest.main()
