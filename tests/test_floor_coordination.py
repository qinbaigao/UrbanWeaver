from copy import deepcopy
from pathlib import Path
from dataclasses import replace
import unittest
from unittest.mock import patch

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.floor_coordination import proposals,apply_proposal,choose_proposal
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.schemas import Room,Door,Bounds2D,Point2D
import test_floor_repartition as fixtures


class FloorCoordinationTests(unittest.TestCase):
    def test_metric_selection_needs_no_model_and_prefers_smallest_shift(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        city=SimpleNamespace(metadata={});service=Mock()
        offers=[{'id':'wide','compatible_after':2,'compatible_before':0,'shift_m':.8},
                {'id':'small','compatible_after':2,'compatible_before':0,'shift_m':-.4},
                {'id':'less_gain','compatible_after':1,'compatible_before':0,'shift_m':.2}]
        choice,attempts=choose_proposal(service,city,offers)
        self.assertEqual(choice['proposal_id'],'small');self.assertEqual(attempts,())
        self.assertFalse(service.mock_calls)
        city.metadata['design_goals']=[{'levels':['floor'],'preference':'private'}]
        self.assertEqual(choose_proposal(None,city,offers)[0]['proposal_id'],'none')

    def fixture(self):
        fixtures.FloorRepartitionTests.setUpClass()
        city,b,f=fixtures.FloorRepartitionTests().fixture()
        x,y=b.footprint.min_x,b.footprint.min_y
        # Two adjacent offices with preserved corridor doors. The 3.6m-wide
        # office is below the private-office reference's 4m minimum.
        f.rooms=[Room(f.id+'_hall','Hall','corridor',Bounds2D(x,y+4.5,x+36,y+24)),
                 Room(f.id+'_a','Office A','office',Bounds2D(x,y,x+3.6,y+4.5)),
                 Room(f.id+'_b','Office B','office',Bounds2D(x+3.6,y,x+9,y+4.5)),
                 Room(f.id+'_rest','Storage','storage',Bounds2D(x+9,y,x+36,y+4.5))]
        f.doors=[Door(f.id+'_da',f.rooms[1].id,f.rooms[0].id,Point2D(x+1.8,y+4.5)),
                 Door(f.id+'_db',f.rooms[2].id,f.rooms[0].id,Point2D(x+6.3,y+4.5)),
                 Door(f.id+'_dr',f.rooms[3].id,f.rooms[0].id,Point2D(x+20,y+4.5)),
                 Door(f.id+'_de',f.rooms[0].id,None,b.entrance,1.8,'exterior')]
        city.world_program=build_world_program(city,producer='test',seed=17)
        library=deepcopy(fixtures.FloorRepartitionTests.lib.room_library)
        # This test exercises a 4 m private-office reference. New compact
        # references must not silently remove the fixture's intended deficit.
        library.rooms={k:v for k,v in library.rooms.items() if k=='office_private_v1'}
        return city,b,f,library

    def test_no_unscoped_or_furnished_coordination(self):
        city,b,f,lib=self.fixture();cfg={'enabled':True}
        self.assertFalse(proposals(city,lib,{},cfg))
        p=proposals(city,lib,{b.id:[0]},cfg);self.assertTrue(p)
        f.rooms[1].object_ids=['accepted_furniture'];f.rooms[2].metadata['locked']=True
        self.assertFalse(proposals(city,lib,{b.id:[0]},cfg))

    def test_adjacent_capacity_gain_preserves_doors_functions_and_compiles(self):
        city,b,f,lib=self.fixture();before=deepcopy(city);cfg={'enabled':True}
        offers=proposals(city,lib,{b.id:[0]},cfg)
        self.assertTrue(offers)
        self.assertTrue(all(r['unfurnished'] and r['major_object_count']==0 for r in offers[0]['rooms']))
        self.assertTrue(all(r['compatible_references_after'] for r in offers[0]['rooms']))
        choice,attempts=choose_proposal(None,city,offers)
        self.assertEqual(attempts,())
        chosen=next(p for p in offers if p['id']==choice['proposal_id'])
        result,report=apply_proposal(city,chosen,lib,GeometryCompiler(),
            authorized_levels={b.id:[0]},config=cfg)
        self.assertEqual(report['status'],'resolved',report)
        after=next(r for r in result.iter_floors() if r.id==f.id)
        self.assertEqual(after.doors,f.doors)
        self.assertEqual([(r.id,r.function) for r in after.rooms],[(r.id,r.function) for r in f.rooms])
        self.assertEqual(city,before)
        with self.assertRaises(ValueError):
            apply_proposal(city,offers[0],lib,GeometryCompiler(),authorized_levels={},config=cfg)

    def test_conflict_targets_the_incompatible_room_not_always_left(self):
        city,b,f,lib=self.fixture();a,c=f.rooms[1:3]
        edge=a.bounds.min_x+5.4
        a.bounds=replace(a.bounds,max_x=edge)
        c.bounds=replace(c.bounds,min_x=edge)
        f.doors[0].position=Point2D(a.bounds.center.x,a.bounds.max_y)
        f.doors[1].position=Point2D(c.bounds.center.x,c.bounds.max_y)
        offers=proposals(city,lib,{b.id:[0]},{'enabled':True})
        self.assertTrue(offers)
        self.assertTrue(all(p['target_room_id']==c.id for p in offers))

    def test_compiled_rejection_does_not_commit_or_mutate_source(self):
        city,b,f,lib=self.fixture();before=deepcopy(city);cfg={'enabled':True}
        offer=proposals(city,lib,{b.id:[0]},cfg)[0]
        with patch('cityg.planning.floor_repartition._check_compiled_access',
                   side_effect=ValueError('blocked access')):
            result,report=apply_proposal(city,offer,lib,GeometryCompiler(),
                authorized_levels={b.id:[0]},config=cfg)
        self.assertNotEqual(report['status'],'resolved')
        self.assertEqual(result,before)
        self.assertEqual(city,before)
