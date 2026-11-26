import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from types import SimpleNamespace

from cityg.planning.generation_coordination import ordered_offers, reserve_larger_sites
from cityg.planning.generation_prototypes import load_options
from cityg.planning.floor_prototype_lab import make_floor_lab
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.schemas import Bounds2D
from cityg.interior_requirements import constrain_reservations


class GenerationCoordinationTests(unittest.TestCase):
    def test_same_shortlist_and_decline_fallback(self):
        offers=[{'id':str(i),'shift_m':i,'compatible_before':0,'compatible_after':1} for i in (3,1,2)]
        for requested,order in [('none',['1','2']),('3',['1','2']),('2',['2','1'])]:
            actual,_=ordered_offers(offers,None,lambda c,o:{'proposal_id':requested},2)
            self.assertEqual([r['id'] for r in actual],order)
        self.assertEqual(len(ordered_offers([],None,None,2)[0]),0)

    def test_area_shortfall_uses_parcel_before_realizing_rooms(self):
        root=Path(__file__).resolve().parents[1]
        city,_=make_floor_lab(FloorPrototypeLibrary(root/'configs/layout_prototypes/v1'),['office_mixed_v1'])
        b=next(city.iter_buildings());p=next(p for p in city.iter_parcels() if b in p.buildings)
        # A small initial shell at the centre of the laboratory parcel.
        c=p.bounds.center;b.footprint=Bounds2D(c.x-4,c.y-4,c.x+4,c.y+4)
        rows={b.id:[{'area_m2':120,'area_basis':'floor_gross'}]}
        target={b.id:{'circulation_axis':'x','entrance_side':'west'}}
        with self.assertRaisesRegex(ValueError,'exceeds buildable area'):
            constrain_reservations(city,target,rows)
        self.assertTrue(reserve_larger_sites(city,target,rows)[0]['accepted'])
        constrain_reservations(city,target,rows)
        self.assertAlmostEqual(Bounds2D(**target[b.id]['footprint']).area,120)
        self.assertAlmostEqual(b.footprint.area,64)

    def test_policy_rejected_at_config_boundary(self):
        source=Path(__file__).resolve().parents[1]/'configs/generation_prototypes.json'
        config=json.loads(source.read_text())
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'settings.json'
            for policy in ['local_only','one_way','fixed_feedback','agent_feedback','bad']:
                config['coordination_policy']=policy;path.write_text(json.dumps(config))
                if policy=='bad':
                    with self.assertRaisesRegex(ValueError,'coordination policy'):load_options(path)
                else:self.assertEqual(load_options(path)['coordination_policy'],policy)

    def test_decline_and_first_rejection_in_production_floor_entry(self):
        from unittest.mock import patch
        from cityg.assets import AssetRegistry
        from cityg.geometry import GeometryCompiler
        from cityg.planning.generation_prototypes import GenerationPrototypes
        from test_floor_coordination import FloorCoordinationTests
        from cityg.ccwp import build_world_program
        root=Path(__file__).resolve().parents[1]
        for policy in ('local_only','one_way','fixed_feedback','agent_feedback'):
            city,b,f,library=FloorCoordinationTests().fixture()
            for floor in city.iter_floors():
                floor.objects.clear()
                for room in floor.rooms:room.object_ids.clear()
            city.world_program=build_world_program(city,producer='test',seed=17)
            config=load_options(root/'configs/generation_prototypes.json')
            config['coordination_policy']=policy
            config['adaptation'].update(max_rooms=1,max_attempts=2)
            config['adaptation']['floor_repartition']['enabled']=False
            runtime=GenerationPrototypes(config)
            runtime.floors.room_library.rooms=library.rooms
            compiler=GeometryCompiler(asset_registry=AssetRegistry(root/'assets/asset_registry.json'))
            registry=runtime.prepare_resources(compiler.asset_registry,compiler)
            seen=[]; decisions=[]
            def decline(_,offered):
                decisions.append([o['id'] for o in offered]);return {'proposal_id':'none'}
            from cityg.planning.floor_coordination import apply_proposal
            def first_rejected(candidate,offer,*args,**kwargs):
                seen.append(offer['id'])
                if len(seen)==1:raise ValueError('test: first candidate invalid')
                return apply_proposal(candidate,offer,*args,**kwargs)
            with patch('cityg.planning.floor_coordination.apply_proposal',side_effect=first_rejected):
                _,report=runtime.populate(city,registry,compiler,building_limit=1,floor_limit=1,
                                         floor_selector=decline)
            self.assertEqual(len(decisions),int(policy=='agent_feedback'))
            self.assertEqual(len(set(seen)),0 if policy in ('local_only','one_way') else 2)
            if policy=='local_only':
                self.assertNotIn('room_dimensions',runtime.floor_context({}))
                self.assertEqual(report['joint_inventory_capacity']['floors'],[])
            if seen:self.assertEqual(report['floor_coordination'][-1]['outcome']['status'],'resolved')
