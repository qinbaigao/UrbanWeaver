from copy import deepcopy
from pathlib import Path
import json
import shutil
from tempfile import TemporaryDirectory
import unittest

from cityg.planning.urban_prototypes import UrbanPrototypeLibrary,realization,topology_snapshot
from cityg.planning.urban_prototype_review import review_views,plan_svg
from cityg.validation import CityValidator

ROOT=Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1'


class UrbanPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=UrbanPrototypeLibrary(ROOT)
        cls.cities={key:cls.lib.plan(key) for key in cls.lib.records}

    def test_twelve_distinct_review_only_recipes(self):
        self.assertEqual(len(self.lib.records),12)
        self.assertEqual(len({self.lib.content_fingerprint(k) for k in self.lib.records}),12)
        for c in self.cities.values():
            self.assertFalse(c.metadata['urban_layout_prototype']['production_enabled'])
            self.assertEqual(c.metadata['interior_scope']['building_levels'],{})
            self.assertFalse(any(c.iter_objects()))

    def test_all_references_pass_realization_and_city_validation(self):
        for k,c in self.cities.items():
            with self.subTest(prototype=k):
                m=realization(c,self.lib.spec(k));self.assertTrue(m['ok'],m)
                report=CityValidator().validate(c);self.assertTrue(report.ok,report.to_dict())

    def test_duplicate_ids_across_library_shards_rejected(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/'library';shutil.copytree(ROOT,root)
            record=self.lib.records['urban_center_v1']
            (root/'urban_duplicate.json').write_text(json.dumps({'schema_version':1,'prototypes':[record]}))
            with self.assertRaisesRegex(ValueError,'duplicate urban'):UrbanPrototypeLibrary(root)

    def test_waterfront_is_local_not_a_city_warp(self):
        c=self.cities['urban_waterfront_v1'];r=realization(c,self.lib.spec('urban_waterfront_v1'))
        self.assertGreaterEqual(r['bridge_count'],1)
        self.assertGreaterEqual(r['morphology']['straight_road_length_ratio'],.65)
        self.assertGreater(r['morphology']['visibly_curved_road_count'],0)
        self.assertGreater(max(v['max_deviation_m'] for v in r['morphology']['rivers'].values()),30)

    def test_clustered_and_irregular_families_are_realized(self):
        for k in ('urban_residential_v1','urban_mixed_v1','urban_campus_v1'):
            self.assertGreater(realization(self.cities[k],self.lib.spec(k))['multi_building_block_count'],0)
        for k in ('urban_center_v1','urban_old_quarter_v1'):
            m=realization(self.cities[k],self.lib.spec(k))
            self.assertGreater(m['polygon_parcel_count'],0)
            self.assertGreater(m['morphology']['junction_degree_counts'].get('3',0),0)

    def test_explicit_adjustments_are_bounded_and_do_not_mutate_recipe(self):
        original=deepcopy(self.lib.records['urban_center_v1'])
        self.assertEqual(self.lib.spec('urban_center_v1',{'building_count':20}).building_count,20)
        for value in ({'building_count':41},{'seed':True},{'road_width_m':2},{'seed':-1}):
            with self.assertRaises(ValueError):self.lib.spec('urban_center_v1',value)
        self.assertEqual(original,self.lib.records['urban_center_v1'])

    def test_reference_repeatability(self):
        key='urban_residential_v1'
        self.assertEqual(topology_snapshot(self.cities[key]),topology_snapshot(self.lib.plan(key)))

    def test_broken_topology_and_quota_do_not_pass_cached_metrics(self):
        c=deepcopy(self.cities['urban_center_v1']);c.districts[0].parcels.pop()
        self.assertFalse(realization(c,self.lib.spec('urban_center_v1'))['checks']['exact_building_count'])
        c=deepcopy(self.cities['urban_center_v1']);c.road_network.segments.clear()
        self.assertFalse(realization(c,self.lib.spec('urban_center_v1'))['checks']['road_graph_connected'])

    def test_public_anchor_and_views_bind_actual_entities(self):
        for c in self.cities.values():
            anchor=c.metadata['urban_layout_prototype']['public_space_anchor_id']
            self.assertIn(anchor,{s['id'] for s in c.metadata['landscape_sites']})
            views=review_views(c)
            self.assertEqual({v['view_id'] for v in views},{'bird','street_1','street_2','feature'})
            self.assertTrue(all(v['render_profile']=='prototype_capture' for v in views))
            self.assertTrue(all(v['mode']=='overview' for v in views))
            for v in views:
                if v['view_id'].startswith('street_'):
                    x,y,_=v['camera_position'];tx,ty,_=v['look_at']
                    center=c.bounds.center
                    self.assertGreaterEqual((tx-x)*(center.x-x)+(ty-y)*(center.y-y),-1e-8)
            self.assertIn('planning envelopes',plan_svg(c))

    def test_floor_reference_update_invalidates_fingerprint(self):
        lib=UrbanPrototypeLibrary(ROOT);key='urban_campus_v1';old=lib.content_fingerprint(key)
        lib.floor_records['office_mixed_v1']['intent']+=' changed'
        self.assertNotEqual(old,lib.content_fingerprint(key))

    def test_capture_resume_requires_completed_matching_views_and_images(self):
        from scripts.build_urban_prototype_review import captures_complete
        views=[{'view_id':'bird','render_profile':'prototype_capture'}]
        with TemporaryDirectory() as temp:
            dest=Path(temp);shots=dest/'screenshots';shots.mkdir()
            self.assertFalse(captures_complete(dest,views))
            report={'exercise_ok':True,'canvas_only':True,'views':[{'spec':views[0]}]}
            (shots/'viewer_smoke.json').write_text(json.dumps(report))
            self.assertFalse(captures_complete(dest,views))
            (shots/'bird.png').touch()
            self.assertTrue(captures_complete(dest,views))
            self.assertFalse(captures_complete(dest,[{**views[0],'fov_deg':60}]))
            report['exercise_ok']=False
            (shots/'viewer_smoke.json').write_text(json.dumps(report))
            self.assertFalse(captures_complete(dest,views))


if __name__=='__main__':unittest.main()
