from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from cityg.agents.room_reference import balanced_candidates, coverage_key, personalize_reference, validate_choice
from cityg.planning.prototypes import LayoutPrototypeLibrary


class RoomReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library=LayoutPrototypeLibrary(Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1')

    def test_balancing_does_not_let_first_building_exhaust_budget(self):
        rows=[]
        for index,(function,room_type) in enumerate([
                ('residential','living_room'),('commercial','office'),('commercial','shop'),
                ('public_service','waiting_room')]):
            for j in range(5):
                b=SimpleNamespace(id=f'b{index}',function=function)
                r=SimpleNamespace(id=f'r{index}_{j}',function=room_type)
                rows.append((b,None,r,[]))
        first=balanced_candidates(rows)[:4]
        self.assertEqual({coverage_key(b,r) for b,_,r,_ in first},
                         {'residential','office','commercial','public_service'})
        self.assertEqual(len(balanced_candidates(rows)),len(rows))

    def test_spacing_patch_retains_assets_inventory_and_protected_structure(self):
        prototype=self.library.materialize('office_private_v1'); before=deepcopy(prototype)
        member=next(m for g in prototype.design.groups for m in g['members'] if .2<=m['gap_m']<=1)
        result=personalize_reference(prototype,[{'member_id':member['id'],'gap_scale':1.1}],.2)
        self.assertEqual(prototype,before)
        self.assertEqual(result.asset_bindings,prototype.asset_bindings)
        a=prototype.design.to_dict(); b=result.design.to_dict()
        for group in b['groups']:
            for m in group['members']:
                if m['id']==member['id']: m['gap_m']/=1.1
        self.assertEqual(a,b)
        for patch in ([{'member_id':member['id'],'gap_scale':1.3}],
                      [{'member_id':'missing','gap_scale':1}],
                      [{'member_id':member['id'],'gap_scale':float('nan')}]):
            with self.assertRaises(ValueError): personalize_reference(prototype,patch,.2)

    def test_selection_binds_candidate_and_original_instruction(self):
        room=SimpleNamespace(id='room',function='office')
        rows=[(SimpleNamespace(id='building',function='commercial'),SimpleNamespace(level=0),room,
               [{'prototype_id':'office_private_v1','quarter_turns':0}])]
        options={'max_rooms':1,'max_buildings':1,'max_floors_per_building':1,'variation_limit':.2}
        choice={'room_id':'room','prototype_id':'office_private_v1','quarter_turns':0,
                'reason':'一个专注工位','requirement_quote':'独立办公室','spacing_adjustments':[]}
        validate_choice({'choices':[choice]},rows,self.library,'需要独立办公室',options)
        for field,value in [('room_id','unknown'),('prototype_id','living_media_v1'),
                            ('quarter_turns',1),('requirement_quote','用户要求十个工位')]:
            with self.assertRaises(ValueError):
                validate_choice({'choices':[{**choice,field:value}]},rows,self.library,'需要独立办公室',options)

