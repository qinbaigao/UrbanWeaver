from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_prototype_lab import make_floor_lab
from cityg.planning.city_prototype_adapter import adapt_city_rooms,architecture,validate_options,verify_room
from cityg.geometry.model import Vec3
from cityg.schemas import Bounds2D

ROOT=Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1'


class CityPrototypeAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=FloorPrototypeLibrary(ROOT)

    def test_certified_bundle_cannot_be_consumed_by_incomplete_reference(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1'])
        b=next(city.iter_buildings());f=b.floors[0];r=next(r for r in f.rooms if r.function!='corridor')
        f.metadata['inventory_capacity']={'status':'references_fit'}
        original=deepcopy(city)
        candidate={'prototype_id':'fixture'}
        def candidates(lib,b,f,room):return [candidate] if room.id==r.id else []
        with patch('cityg.planning.city_prototype_adapter.room_candidates',side_effect=candidates), \
             patch('cityg.refinement.inventory_allocation.allocate_remaining_inventory',return_value={r.id:[{'category':'meeting_chair','min_count':6}]}), \
             patch('cityg.planning.prototype_inventory.prioritize_inventory',side_effect=lambda cs,*args:cs), \
             patch('cityg.planning.city_prototype_adapter.populate_adapted_room',return_value={'major_count':0}):
            result,report=adapt_city_rooms(city,self.lib,None,None,{'max_attempts':1})
        self.assertEqual(city,original)
        self.assertEqual(list(result.iter_buildings()),list(original.iter_buildings()))
        self.assertFalse(report['rooms'])
        self.assertIn('incomplete furniture bundle',report['attempts'][0]['reason'])

    def test_budgets_fail_closed(self):
        for options in ({'max_rooms':0},{'max_rooms':True},{'max_rooms':12.5},
                        {'max_attempts':0},{'max_attempts':True},{'max_attempts':float('inf')},
                        {'max_attempts_per_room':0},{'max_attempts_per_room':True},
                        {'variation_limit':float('nan')},{'other':1}):
            with self.assertRaises(ValueError):validate_options(options)

    def test_room_budget_scales_without_ten_room_cap(self):
        self.assertEqual(validate_options({})['max_rooms'],10)
        for count in (16,40,100):
            opt=validate_options({'max_rooms':count})
            self.assertEqual(opt['max_rooms'],count)
            self.assertEqual(opt['max_attempts'],3*count)
            self.assertEqual(validate_options(opt),opt)
        self.assertEqual(validate_options({'max_rooms':60,'max_attempts':12})['max_attempts'],12)
        self.assertEqual(validate_options({'max_rooms':60,'max_attempts':None,
                                          'max_attempts_per_room':2})['max_attempts'],120)

    def test_rejected_room_does_not_starve_later_room(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1'])
        first=next(city.iter_buildings()).floors[0]
        targets=[r for r in first.rooms if r.function!='corridor'][:2]
        original=deepcopy(city)
        def candidates(lib,b,f,r):
            return [{'prototype_id':f'fixture_{i}'} for i in range(8)] if r.id in {q.id for q in targets} else []
        def populate(city,b,f,room,*args,**kwargs):
            room.metadata['changed']=True
            if room.id==targets[0].id:raise ValueError('incompatible')
            return {'room_id':room.id,'building_id':b.id,'floor_id':f.id,'major_count':1}
        with patch('cityg.planning.city_prototype_adapter.room_candidates',side_effect=candidates), \
             patch('cityg.planning.city_prototype_adapter.populate_adapted_room',side_effect=populate), \
             patch('cityg.planning.city_prototype_adapter.CityValidator') as validator, \
             patch('cityg.planning.city_prototype_adapter.verify_room',return_value=[{'ok':True}]):
            validator.return_value.validate.return_value.ok=True
            _,report=adapt_city_rooms(city,self.lib,None,SimpleNamespace(compile=lambda *a,**kw:None),
                {'max_rooms':16,'max_attempts_per_room':2})
        self.assertEqual(city,original)
        self.assertEqual(sum(a['room_id']==targets[0].id for a in report['attempts']),2)
        self.assertIn(targets[0].id,report['room_budget_exhausted'])
        self.assertEqual([r['room_id'] for r in report['rooms']],[targets[1].id])

    def test_adapter_loop_can_commit_more_than_ten_rooms(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1'])
        original=deepcopy(city)
        def populate(city,b,f,room,*args,**kwargs):
            room.metadata['reviewed_candidate']=True
            return {'room_id':room.id,'building_id':b.id,'floor_id':f.id,'major_count':1}
        with patch('cityg.planning.city_prototype_adapter.room_candidates',return_value=[{'prototype_id':'fixture'}]), \
             patch('cityg.planning.city_prototype_adapter.populate_adapted_room',side_effect=populate), \
             patch('cityg.planning.city_prototype_adapter.CityValidator') as validator, \
             patch('cityg.planning.city_prototype_adapter.verify_room',return_value=[{'ok':True}]):
            validator.return_value.validate.return_value.ok=True
            _,report=adapt_city_rooms(city,self.lib,None,SimpleNamespace(compile=lambda *a,**kw:None),
                                     {'max_rooms':12})
        self.assertEqual(city,original)
        self.assertEqual(len(report['rooms']),12)
        self.assertEqual(report['stop_reason'],'target_reached')

    def test_compiled_failure_restores_scope_inventory_and_source(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1'])
        b=next(city.iter_buildings());f=b.floors[0];r=f.rooms[1]
        city.metadata['interior_scope']={'building_levels':{},'policy':'test'}
        original=deepcopy(city)
        candidate={'prototype_id':'fixture'}
        def candidates(lib,b,f,room):return [candidate] if room.id==r.id else []
        def populate(city,b,f,room,*args,**kwargs):
            room.metadata['changed']=True;f.objects[:]=[];room.object_ids.clear()
            return {'room_id':room.id,'building_id':b.id,'floor_id':f.id,'major_count':1}
        with patch('cityg.planning.city_prototype_adapter.room_candidates',side_effect=candidates), \
             patch('cityg.planning.city_prototype_adapter.populate_adapted_room',side_effect=populate), \
             patch('cityg.planning.city_prototype_adapter.CityValidator') as validator, \
             patch('cityg.planning.city_prototype_adapter.verify_room',side_effect=ValueError('compiled_rejection')):
            validator.return_value.validate.return_value.ok=True
            result,report=adapt_city_rooms(city,self.lib,None,SimpleNamespace(compile=lambda *a,**kw:None))
        self.assertEqual(city,original);self.assertEqual(list(result.iter_buildings()),list(original.iter_buildings()))
        self.assertEqual(result.metadata['interior_scope'],original.metadata['interior_scope'])
        self.assertEqual(result.world_program,original.world_program)
        self.assertEqual(report['summary']['accepted_rooms'],0)
        self.assertEqual(report['attempts'][0]['reason'],'compiled_rejection')

    def test_success_keeps_ids_geometry_and_unrelated_rooms(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1']);b=next(city.iter_buildings());target=b.floors[0].rooms[1]
        city.metadata['interior_scope']={'building_levels':{b.id:[1]},'policy':'test'};original=deepcopy(city)
        def populate(city,b,f,room,*args,**kwargs):
            room.metadata['reviewed_candidate']=True
            return {'room_id':room.id,'building_id':b.id,'floor_id':f.id,'major_count':1}
        with patch('cityg.planning.city_prototype_adapter.room_candidates',side_effect=lambda l,b,f,r:[{'prototype_id':'fixture'}] if r.id==target.id else []), \
             patch('cityg.planning.city_prototype_adapter.populate_adapted_room',side_effect=populate), \
             patch('cityg.planning.city_prototype_adapter.CityValidator') as validator, \
             patch('cityg.planning.city_prototype_adapter.verify_room',return_value=[{'ok':True}]):
            validator.return_value.validate.return_value.ok=True
            result,report=adapt_city_rooms(city,self.lib,None,SimpleNamespace(compile=lambda *a,**kw:None))
        self.assertEqual(city,original);self.assertEqual(architecture(result),architecture(original))
        self.assertEqual(result.metadata['interior_scope']['building_levels'][b.id],[0,1])
        self.assertEqual(report['summary']['accepted_rooms'],1)
        after=next(result.iter_buildings())
        self.assertEqual(after.floors[1],b.floors[1]);self.assertEqual(after.vertical_connectors,b.vertical_connectors)
        self.assertEqual(report['whole_floor_replacements'],0)

    def test_world_rotated_containment_uses_building_local_frame(self):
        from cityg.geometry.model import GeometryPrimitive
        # A local (2, 0) center becomes world (10, 12) at yaw +90.
        bounds=Bounds2D(10,9,14,11)
        building=SimpleNamespace(footprint=Bounds2D(5,5,15,15),metadata={'orientation_deg':90})
        room=SimpleNamespace(id='room',metadata={'room_design':{'zones':[]}})
        floor=SimpleNamespace(objects=[SimpleNamespace(id='obj',room_id='room',metadata={})])
        p=GeometryPrimitive(id='mesh',owner_id='obj',primitive_type='box',center=Vec3(10,12,1),size=Vec3(1,1,1),
            rotation_z_deg=90,semantic_class='furniture_desk',material_id='mat',layer_id='floor:f')
        scene=SimpleNamespace(primitives=[p],metadata={})
        row={'major_count':1,'expected_inventory':{}}
        with patch('cityg.planning.city_prototype_adapter.metric_envelope',return_value={'status':'supported','bounds':bounds}):
            self.assertTrue(all(c['ok'] for c in verify_room(scene,building,floor,room,row)))
            p.center=Vec3(10,20,1)
            with self.assertRaises(ValueError):verify_room(scene,building,floor,room,row)


if __name__=='__main__':unittest.main()
