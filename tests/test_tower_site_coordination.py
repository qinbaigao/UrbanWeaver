import json
import unittest

from tower_edit_fixtures import fixture, run
from cityg.editing import _apply_replans
from cityg.geometry import GeometryCompiler
from cityg.planning.site_coordination import FloorCapacityConflict
from cityg.transactions import fingerprint


class LocalDecisions:
    """Exercise the same constrained proposal protocol without needing a GPU."""
    def complete(self, messages, schema):
        return json.dumps({'action': schema['properties']['action']['enum'][0], 'reason': 'regression fixture'})


class TowerCoordinationTests(unittest.TestCase):
    def test_furnished_partition_and_fixed_area_shape_edits(self):
        for case in ('meeting_area', 'conference_depth'):
            with self.subTest(case=case):
                self.assertEqual(run(case, LocalDecisions(), 'fixture'), 'accepted')

    def test_parcel_screening_recovers_conference_depth_without_losing_furniture(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from cityg.memory import MemoryRecord, MemoryStore
        for fraction in (.96, .86):
            city, b, f, r = fixture('conference_depth')
            with self.subTest(fraction=fraction), TemporaryDirectory() as tmp, MemoryStore(Path(tmp)/'m.db') as store:
                store.put(MemoryRecord('prior','geometry_check','entity',r.id,{'dependency_entity_ids':[f.id]},
                                       validation_status='accepted'))
                request = {'area_m2':fraction*b.footprint.area, 'allow_aspect_adjustment':True}
                updated, _, traces = _apply_replans(city,[{'kind':'building_site','target_id':b.id,'details':request}],
                    LocalDecisions(), model_id='fixture',asset_resolver=None,room_compiler=GeometryCompiler(),
                    memory_store=store)
                report=traces[0]['transaction']
                self.assertEqual(report['status'],'accepted')
                self.assertEqual(store.get('prior').validation_status,'stale')
                self.assertTrue(report['compiled_gate']['room_retention']['ok'])
                actual=next(t for t in updated.iter_buildings() if t.id==b.id)
                self.assertAlmostEqual(actual.footprint.area,request['area_m2'])
                self.assertIn(f.id,report['compiled_gate']['compiled_access_floors'])

    def test_failed_compiled_candidate_can_retry_before_publishing(self):
        from unittest.mock import patch
        from cityg.editing import _site_compile_receipt
        city,b,_,_=fixture('meeting_area')
        observed=[]
        def check(source, candidate, *args):
            shape=next(t.footprint for t in candidate.iter_buildings() if t.id==b.id)
            observed.append(shape)
            if len(observed)==1:
                return {'ok':False}
            return _site_compile_receipt(source,candidate,*args)
        request={'area_m2':.96*b.footprint.area,'allow_aspect_adjustment':True}
        with patch('cityg.editing._site_compile_receipt',side_effect=check):
            updated,_,traces=_apply_replans(city,[{'kind':'building_site','target_id':b.id,'details':request}],
                LocalDecisions(),model_id='fixture',asset_resolver=None,room_compiler=GeometryCompiler())
        self.assertLessEqual(len(observed),3)
        self.assertNotEqual(observed[0],observed[-1])
        self.assertEqual(next(t.footprint for t in updated.iter_buildings() if t.id==b.id),observed[-1])
        self.assertTrue(traces[0]['transaction']['compiled_gate']['ok'])

    def test_fixed_aspect_conflict_does_not_publish(self):
        city, building, _, _ = fixture('conference_depth')
        source = fingerprint(city)
        with self.assertRaises(FloorCapacityConflict):
            _apply_replans(city, [{'kind':'building_site', 'target_id':building.id,
                                  'details':json.dumps({'area_m2':.8*building.footprint.area})}],
                           LocalDecisions(), model_id='fixture', asset_resolver=None, room_compiler=GeometryCompiler())
        self.assertEqual(fingerprint(city), source)
