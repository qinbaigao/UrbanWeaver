import json
from pathlib import Path
import tempfile
import unittest

from cityg.assets import AssetRecord, AssetRegistry
from cityg.planning.prototypes import LayoutPrototypeLibrary, reference_registry
from cityg.planning.prototype_lab import make_lab, compiled_containment_checks
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.interiors import ASSET_CATALOG
from cityg.ccwp import build_world_program
from cityg.validation import CityValidator


ROOT = Path(__file__).resolve().parents[1] / 'configs/layout_prototypes/v1'


class LayoutPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.library = LayoutPrototypeLibrary(ROOT)

    def test_all_drafts_are_well_formed_but_not_production_candidates(self):
        self.assertTrue({'living_crossbay_dining_v1','bedroom_crossbay_wardrobe_v1',
                         'cafe_service_pantry_v1','reception_cafe_waiting_v1','shop_shallow_counter_v1'} <= self.library.rooms.keys())
        self.assertEqual(len(self.library.rooms), 61)
        self.assertEqual(len(self.library.combinations), 43)
        for key, record in self.library.rooms.items():
            materialized = self.library.materialize(key)
            materialized.program('room').validate(ASSET_CATALOG)
            params = {k: record['reference'][k] for k in ('width_m','depth_m','height_m')}
            self.assertNotIn(key, self.library.candidates(room_type=record['room_type'], **params))
            self.assertIn(key, self.library.candidates(include_unapproved=True, room_type=record['room_type'], **params))
            with self.assertRaisesRegex(ValueError, 'approval'):
                self.library.materialize(key, for_production=True)

    def test_scoped_combination_ids_and_support_binding(self):
        design = self.library.materialize('office_four_v1').design
        members = [i['id'] for g in design.groups for i in [g['anchor'], *g['members']]]
        self.assertEqual(len(members), len(set(members)))
        self.assertTrue(all(p['support_member_id'] in members for p in design.surface_items))
        self.assertEqual(sum(i['category']=='desk' for g in design.groups for i in [g['anchor'],*g['members']]), 4)

    def test_compact_batch_keeps_capacity_roles_and_review_boundaries(self):
        from collections import Counter
        for key,expected in [('office_open_four_compact_v1',{'desk':4,'office_chair':4}),
                             ('meeting_six_compact_v1',{'meeting_table':1,'meeting_chair':6}),
                             ('living_dining_shallow_v1',{'sofa':1,'dining_table':1,'dining_chair':4}),
                             ('storage_linear_shallow_v1',{'storage_rack':3}),
                             ('restroom_compact_v1',{'toilet':1,'sink':1})]:
            design=self.library.materialize(key).design
            counts=Counter(i['category'] for g in design.groups for i in [g['anchor'],*g['members']])
            for category,n in expected.items():self.assertEqual(counts[category],n)
            self.assertFalse(self.library.approved(key))
        for key in ('office_open_four_compact_v1','bedroom_study_shallow_v1'):
            record=self.library.rooms[key]
            for case in [record['reference'],*record['adaptation_cases']]:
                self.assertTrue(self.library.compatible(key,room_type=record['room_type'],
                    **{k:case[k] for k in ('width_m','depth_m','height_m')}))

    def test_caller_cannot_mutate_source_through_materialized_design(self):
        materialized = self.library.materialize('office_private_v1')
        materialized.design.groups[0]['members'].clear()
        self.assertEqual(len(self.library.materialize('office_private_v1').design.groups[0]['members']), 1)

    def test_review_invalidation_tracks_dependency_changes(self):
        key = 'office_private_v1'
        for combo in self.library.rooms[key]['group_instances']:
            c = combo['combination']
            self.library.combinations[c]['review'] = {'status':'approved','reviewer':'test_human',
                'reviewed_fingerprint':self.library.content_fingerprint(c)}
        self.library.rooms[key]['review'] = {'status':'approved','reviewer':'test_human',
            'reviewed_fingerprint':self.library.content_fingerprint(key)}
        self.assertTrue(self.library.approved(key))
        self.library.combinations['workstation']['members'][0]['gap_m'] = .5
        self.assertFalse(self.library.approved(key))

    def test_compatibility_rejects_wrong_function_door_and_dimensions(self):
        params = dict(room_type='bedroom', width_m=5.2, depth_m=4.8,height_m=3.2)
        self.assertTrue(self.library.compatible('bedroom_double_v1', **params))
        for changes in ({'room_type':'office'}, {'door_wall':'north'}, {'width_m':2},
                        {'width_m':float('nan')}, {'height_m':2}):
            self.assertFalse(self.library.compatible('bedroom_double_v1', **{**params,**changes}))

    def test_decoration_annotation_changes_invalidate_room_fingerprint(self):
        before=self.library.content_fingerprint('bedroom_double_v1')
        self.library.decoration_assets[0]['scale']=1.0
        self.assertNotEqual(before,self.library.content_fingerprint('bedroom_double_v1'))

    def test_lab_uses_real_dimensions_and_valid_access(self):
        city, targets = make_lab(self.library, list(self.library.rooms)[:6])
        for key, building, floor, room in targets:
            envelope = metric_envelope(building, floor, room)
            ref = self.library.rooms[key]['reference']
            self.assertEqual(envelope['status'], 'supported')
            self.assertAlmostEqual(envelope['bounds'].width, ref['width_m'])
            self.assertAlmostEqual(envelope['bounds'].depth, ref['depth_m'])
            self.assertAlmostEqual(envelope['floor'].doors[0].width_m, ref['door_width_m'])
        city.world_program = build_world_program(city,producer='test',seed=17)
        report = CityValidator().validate(city)
        self.assertTrue(report.ok, report.to_dict())

    def test_expansion_functions_and_pinned_dependencies(self):
        functions = {r['room_type'] for r in self.library.rooms.values()}
        self.assertTrue({'reading_room','reception','kitchen','bathroom','shop'} <= functions)
        before = self.library.content_fingerprint('bathroom_shower_v1')
        old = self.library.content_fingerprint('bedroom_double_v1')
        annotation = next(a for a in self.library.reference_assets if a['id']=='prototype_shower_complete')
        annotation['front_axis'] = '-X'
        self.assertNotEqual(before, self.library.content_fingerprint('bathroom_shower_v1'))
        self.assertEqual(old, self.library.content_fingerprint('bedroom_double_v1'))

    def test_large_review_fixtures_are_disjoint_and_inside_their_parcels(self):
        keys=['office_open_twelve_v1','coworking_open_v1','retail_open_hall_v1','mall_open_lounge_v1']
        city,targets=make_lab(self.library,keys)
        buildings=list(city.iter_buildings())
        for parcel in city.districts[0].parcels:
            self.assertTrue(parcel.bounds.contains_bounds(parcel.buildings[0].footprint))
        for i,a in enumerate(buildings):
            for b in buildings[i+1:]:self.assertFalse(a.footprint.overlaps_area(b.footprint))
        for key,b,f,r in targets:
            self.assertGreaterEqual(metric_envelope(b,f,r)['bounds'].area,160)
            self.assertTrue(self.library.materialize(key).design.reserved_areas)

    def test_sharded_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for filename in ('rooms.json','combinations.json'):
                (root/filename).write_text((ROOT/filename).read_text())
            (root/'rooms_duplicate.json').write_text((ROOT/'rooms.json').read_text())
            with self.assertRaisesRegex(ValueError,'duplicate'):
                LayoutPrototypeLibrary(root)

    def test_review_inventory_detects_incomplete_nominal_props(self):
        from scripts.build_layout_prototype_review import inventory_checks
        from types import SimpleNamespace
        scene = SimpleNamespace(metadata={'room_surface_items':{'r':{'requested':2,'placed':1}}})
        checks = inventory_checks(scene,[{'room_id':'r','prototype_id':'test'}])
        self.assertFalse(all(c['ok'] for c in checks))
        scene.metadata['room_surface_items']['r']['placed']=2
        self.assertTrue(all(c['ok'] for c in inventory_checks(scene,[{'room_id':'r','prototype_id':'test'}])))
        scene.metadata.clear()
        row={'room_id':'r','prototype_id':'test','expected_inventory':{'room_surface_items':2}}
        self.assertFalse(all(c['ok'] for c in inventory_checks(scene,[row])))

    def test_missing_asset_is_not_silently_replaced(self):
        with self.assertRaisesRegex(ValueError, 'Missing/incompatible'):
            reference_registry(AssetRegistry(), self.library.materialize('bedroom_double_v1'))

    def test_asset_registry_is_detached_and_semantic_bindings_enforced(self):
        p = self.library.materialize('bedroom_double_v1')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'fixture.glb'
            path.write_bytes(b'test fixture only')
            source = AssetRegistry()
            for category, asset in p.asset_bindings.items():
                source.register(AssetRecord(asset, category, geometry_path=str(path),
                    dimensions_m=(1,1,1), environment='indoor',room_types=('bedroom',)))
            detached = reference_registry(source,p)
            self.assertIsNot(source, detached)
            self.assertEqual(len(detached.list_all()), len(p.asset_bindings))
            bad = next(iter(p.asset_bindings.values()))
            source.register(AssetRecord(bad,'sofa',geometry_path=str(path),dimensions_m=(1,1,1)),overwrite=True)
            with self.assertRaises(ValueError):reference_registry(source,p)

    def test_duplicate_ids_and_false_approval_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for filename in ('rooms.json','combinations.json'):
                (root/filename).write_text((ROOT/filename).read_text())
            doc = json.loads((root/'rooms.json').read_text())
            doc['prototypes'][0]['review'] = {'status':'approved'}
            (root/'rooms.json').write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'reviewer'):LayoutPrototypeLibrary(root)
            doc['prototypes'][0]['review'] = {'status':'pending_review'}
            doc['prototypes'].append(doc['prototypes'][0])
            (root/'rooms.json').write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'duplicate'):LayoutPrototypeLibrary(root)

    def test_declared_table_role_is_local_and_preserves_physical_size(self):
        prototype = self.library.materialize('meeting_six_v1')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'table.glb'
            path.write_bytes(b'fixture')
            source = AssetRegistry()
            for category, asset in prototype.asset_bindings.items():
                original = 'dining_table' if category == 'meeting_table' else category
                rooms = ('break_room',) if original == 'dining_table' else ('meeting_room',)
                source.register(AssetRecord(asset, original, geometry_path=str(path),
                                            dimensions_m=(2.2,1.1,.75), room_types=rooms, environment='indoor'))
            pinned = reference_registry(source, prototype)
            key = prototype.asset_bindings['meeting_table']
            self.assertEqual(source.get(key).category, 'dining_table')
            self.assertEqual(source.get(key).room_types, ('break_room',))
            self.assertEqual(pinned.get(key).category, 'meeting_table')
            self.assertEqual(pinned.get(key).dimensions_m, source.get(key).dimensions_m)

    def test_door_crossing_corner_and_unsupported_role_are_rejected(self):
        record = self.library.rooms['bedroom_double_v1']
        record['reference']['door_fraction'] = .05
        with self.assertRaisesRegex(ValueError,'corner'): self.library._validate_room(record)
        self.library.combinations['meeting_six']['asset_roles']['meeting_table']['source_category'] = 'sofa'
        with self.assertRaisesRegex(ValueError,'Unsupported'): self.library.materialize('meeting_six_v1')

    def test_compiled_containment_detects_missing_and_escaped_objects(self):
        from cityg.schemas import InteriorObject, Point2D
        from cityg.geometry.model import GeometryScene, GeometryPrimitive, Vec3
        _, targets = make_lab(self.library,['office_private_v1'])
        key, b, f, r = targets[0]
        obj = InteriorObject('object',r.id,'desk','fixture',r.bounds.center,1,1,1)
        f.objects.append(obj)
        scene = GeometryScene('fixture','z_up')
        self.assertFalse(compiled_containment_checks(scene,targets)[0]['ok'])
        center = metric_envelope(b,f,r)['bounds'].center
        primitive = GeometryPrimitive('p',obj.id,'box',Vec3(center.x,center.y,.5),
                                      Vec3(1,1,1),0,'furniture_desk','wood','floor')
        scene.primitives.append(primitive)
        self.assertTrue(compiled_containment_checks(scene,targets)[0]['ok'])
        primitive.center = Vec3(10000,10000,.5)
        self.assertFalse(compiled_containment_checks(scene,targets)[0]['ok'])


if __name__ == '__main__':
    unittest.main()
