import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from cityg.assets import AssetRecord, AssetRegistry, AssetResolver
from cityg.schemas import Building, Bounds2D, Point2D, Room, Floor, InteriorObject
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.furnishing_sufficiency import assess_furnishing
from cityg.planning.interiors import FloorDetailAgent, ASSET_CATALOG


class FurnishingSufficiencyTests(unittest.TestCase):
    def setUp(self):
        self.room=Room('r','office','office',Bounds2D(0,0,10,10))
        self.floor=Floor('f',0,0,3,rooms=[self.room])
        self.building=Building('b','test','commercial',Bounds2D(0,0,10,10),Point2D(5,0),floors=[self.floor])
        self.frame={'rotation':0,'cos':1,'sin':0,'min_x':-5,'max_x':5,'min_y':-5,'max_y':5,
                    'parts':[{'min_x':-5,'max_x':0,'min_y':-5,'max_y':5,'height_scale':1},
                             {'min_x':0,'max_x':5,'min_y':0,'max_y':5,'height_scale':1}]}

    def test_concavity_cannot_be_filled_by_bounding_box(self):
        self.building.metadata['massing_style'] = 'l_shape'
        with patch('cityg.geometry.compiler.GeometryCompiler._massing_frame',return_value=self.frame):
            result=metric_envelope(self.building,self.floor,self.room)
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['area_m2'],75)

    def test_plain_shell_does_not_invent_massing_clipping(self):
        with patch('cityg.geometry.compiler.GeometryCompiler._massing_frame', side_effect=AssertionError('unused')):
            result=metric_envelope(self.building,self.floor,self.room)
        self.assertEqual(result['status'],'supported')
        self.assertEqual(result['area_m2'],100)

    def test_exterior_envelope_is_not_treated_as_box_interior(self):
        with patch('cityg.envelopes.envelope_config',return_value={'shape':'ellipse'}):
            result=metric_envelope(self.building,self.floor,self.room)
        self.assertEqual(result['reason'],'exterior_only_envelope')

    def test_rectangular_room_in_multipart_building_has_true_metric_area(self):
        room=replace(self.room,bounds=Bounds2D(0,0,5,10))
        with patch('cityg.geometry.compiler.GeometryCompiler._massing_frame',return_value=self.frame):
            result=metric_envelope(self.building,self.floor,room)
        self.assertEqual(result['status'],'supported')
        self.assertEqual(result['area_m2'],50)
        self.assertEqual(room.bounds,Bounds2D(0,0,5,10))

    def test_sparsity_is_advisory_and_does_not_insert_objects(self):
        objects=[InteriorObject('desk','r','desk','desk',Point2D(2,2),1.5,.7,.75)]
        before=deepcopy(objects)
        report=assess_furnishing(self.room,objects,area_m2=40,
            surface_report={'requested':8,'placed':1,'skipped':[{'reason':'no_verified_surface'}]})
        self.assertTrue(report['needs_review'])
        self.assertIn('support_dressing_low_realization',report['reasons'])
        self.assertEqual(objects,before)
        self.assertTrue(report['candidate_functional_bundles'])

    def test_resolver_prefers_verified_support_without_inventing_one(self):
        registry=AssetRegistry()
        for aid,supports in [('a_no_surface',[]),('b_with_surface',[
                {'kind':'top','verified':True,'center':[0,0,.5],'size':[.8,.8]}])]:
            registry.register(AssetRecord(aid,'desk',geometry_path=aid+'.glb',
                dimensions_m=(1.5,.7,.75),environment='indoor',room_types=('office',),
                metadata={'room_support_surfaces':supports,'runtime_enabled':True}))
        detail=FloorDetailAgent(asset_resolver=AssetResolver(registry,(),max_provider_calls=0))
        asset=detail._resolve_asset(ASSET_CATALOG['desk'],room_type='office',support_kinds={'top'})
        self.assertEqual(asset.id,'b_with_surface')
        self.assertEqual((asset.width_m,asset.depth_m,asset.height_m),(1.5,.7,.75))

    def test_bounded_second_pass_keeps_first_feasible_program_on_failure(self):
        self._check_bounded_review_fallback()

    def test_completion_capacity_review_cannot_lose_accepted_furniture(self):
        self._check_bounded_review_fallback(completion=True)

    def _check_bounded_review_fallback(self, completion=False):
        from test_room_enrichment import fixture_design
        from cityg.refinement.room import RoomProgramAgent
        design=fixture_design()
        if completion:design=replace(design,surface_items=())
        payload={'room_id':'r','style':'warm','density':.4,'requests':[],'design':design.to_dict()}
        class Service:
            def __init__(self): self.calls=[]
            def complete(self,messages,schema=None):
                self.calls.append(messages[:])
                return json.dumps(payload)
        service=Service()
        objects=[InteriorObject('desk','r','desk','desk',Point2D(2,2),1.5,.7,.75),
                 InteriorObject('chair','r','office_chair','chair',Point2D(2,3),.5,.5,.8)]
        resolver=AssetResolver(AssetRegistry(),(),max_provider_calls=0)
        agent=RoomProgramAgent(service,asset_resolver=resolver,max_attempts=2)
        envelope={'status':'supported','source':'test','canonical_area_m2':100,'area_m2':100,
                  'bounds':self.room.bounds,'room':self.room,'floor':self.floor}
        with patch('cityg.refinement.room.metric_envelope',return_value=envelope), \
             patch('cityg.planning.room_metric_frame.place_metric_room',side_effect=[objects,objects[:1]]):
            options={} if not completion else {
                'visual_feedback':{'major_inventory_only':True,'allow_capacity_review':True},
                'inventory_targets':[{'room_function':'office','category':c,'min_count':1}
                                     for c in ('desk','office_chair')]}
            result=agent.propose(SimpleNamespace(name='test'),self.building,self.floor,self.room,**options)
        self.assertEqual(len(service.calls),2)
        self.assertEqual(len(result.attempts),2)
        self.assertIn('_sufficiency_fallback',result.raw)
        self.assertEqual(result.program.requested_major_count,2)
        self.assertEqual(self.floor.objects,[])
        self.assertIn('ONE bounded',service.calls[1][-1].content)

    def test_unsupported_room_does_not_spend_model_calls(self):
        from cityg.refinement.room import RoomProgramAgent
        service=SimpleNamespace(complete=lambda *args: self.fail('Must not call model'))
        agent=RoomProgramAgent(service,asset_resolver=AssetResolver(AssetRegistry(),(),max_provider_calls=0))
        with patch('cityg.refinement.room.metric_envelope',return_value={'status':'unavailable','reason':'empty'}):
            with self.assertRaisesRegex(ValueError,'floor-level replanning'):
                agent.propose(SimpleNamespace(name='test'),self.building,self.floor,self.room)

    def test_support_probe_dry_run_does_not_write_production_registry(self):
        from scripts.complete_room_supports import complete
        self.room.metadata={'detail_tier':'hero','room_design':{'surface_items':[
            {'support_member_id':'desk','surface':'top'}]}}
        self.floor.objects=[InteriorObject('o','r','desk','asset',Point2D(2,2),1.5,.7,.75,
                                          metadata={'design_member_id':'desk'})]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); mesh=root/'desk.glb';mesh.write_bytes(b'fixture')
            path=root/'registry.json';registry=AssetRegistry(path)
            registry.register(AssetRecord('asset','desk',geometry_path=str(mesh),dimensions_m=(1.5,.7,.75)))
            before=path.read_bytes()
            with patch('scripts.complete_room_supports.load_city',return_value=SimpleNamespace(iter_buildings=lambda:[self.building])), \
                 patch('scripts.complete_room_supports.triangles',return_value=None), \
                 patch('scripts.complete_room_supports.discover_supports',return_value=([
                     {'id':'top_00','kind':'top','verified':True,'center':[0,0,.5],'size':[.8,.8]}],[])):
                report=complete(root/'city.json',path,root/'dry_run')
            self.assertTrue(report[0]['added'])
            self.assertEqual(path.read_bytes(),before)
            candidate=AssetRegistry(root/'dry_run/candidate_registry.json')
            self.assertTrue(candidate.require('asset').metadata['room_support_surfaces'])
            self.assertTrue(candidate.resolve_path(candidate.require('asset').geometry_path).is_file())
