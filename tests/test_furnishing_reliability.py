import json
import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from cityg.agents.requirement import RequirementAgent
from cityg.agents.interior_requirement import apply_coverage_review
from cityg.planning.functional_seeds import inventory_programs
from cityg.planning.room_design import RoomDesign
from cityg.planning.interiors import ASSET_CATALOG
from cityg.schemas import Room, Bounds2D
from test_interior_requirements import requirement
from test_requirement_agent import FakeService, VALID_SPEC


class FurnishingReliabilityTests(unittest.TestCase):
    def test_reference_limits_do_not_turn_into_generation_exceptions(self):
        room=Room('r','Meeting','meeting_room',Bounds2D(0,0,20,20))
        for inventory in [
            [{'category':'meeting_table','min_count':1},{'category':'meeting_chair','min_count':9}],
            [{'category':'cabinet','min_count':17}],
        ]:
            self.assertEqual(list(inventory_programs(room,inventory)),[])

    def test_arrow_cycle_normalization_preserves_unknown_function_errors(self):
        from cityg.planning.programs import _normalize_floor_cycle
        self.assertEqual(_normalize_floor_cycle('shop -> break_room → storage','commercial'),
                         ('shop','break_room','storage'))
        self.assertIn('imaginary',_normalize_floor_cycle('shop -> imaginary','commercial'))

    def test_asset_context_keeps_procedural_geometry_when_no_mesh_is_available(self):
        from types import SimpleNamespace
        from cityg.planning.floor_inventory_capacity import inventory_asset_context
        b=SimpleNamespace(metadata={'interior_layout_contract':{'requirements':[requirement()]}})
        with patch('cityg.planning.interiors.FloorDetailAgent._resolve_asset',return_value=None):
            result=inventory_asset_context(b,None)
        self.assertEqual(result[0]['geometry_source'],'procedural_catalog')
        self.assertEqual(result[0]['dimensions_m'][0],ASSET_CATALOG['desk'].width_m)

    def test_separate_extraction_adds_grounded_omission_and_city_cannot_change_ledger(self):
        row=requirement();row['source_quote']='A ground floor 160 m2 office with 2 desks and office chairs.'
        missing={'missing_items':[{'room_function':'office','category':'office_chair',
                                  'min_count':1,'source_quote':'office chairs'}]}
        city=deepcopy(VALID_SPEC)
        malicious={**city,'interior_requirements':[]}
        service=FakeService([json.dumps({'interior_requirements':[row]}),json.dumps(missing),
                             json.dumps({"indices":[]}),json.dumps(malicious),json.dumps(city)])
        result=RequirementAgent(service,separate_interiors=True).parse(row['source_quote'])
        self.assertEqual(len(result.attempts),5)
        self.assertIn('cannot overwrite',result.attempts[3].error)
        self.assertEqual([i['category'] for i in result.spec.interior_requirements[0]['inventory']],['desk','office_chair'])
        self.assertNotIn('interior_requirements',service.calls[-1][1]['properties'])

    def test_scope_keeps_explicit_city_relations_after_empty_selection(self):
        from cityg.agents.urban_scope import urban_scope
        instruction=('Provide a waiting area near the entrance. Place housing north of the offices. '
                     'Add a public green space.')
        clauses,trace=urban_scope(instruction, FakeService(['{"indices":[]}']))
        self.assertEqual(clauses,['Place housing north of the offices.'])
        self.assertIsNone(trace.error)
        clauses,trace=urban_scope(instruction, FakeService(['{"indices":[100]}']))
        self.assertIsNone(clauses)
        self.assertTrue(trace.error)

    def test_audit_cannot_change_explicit_count_or_bind_to_other_building(self):
        row=requirement()
        review={'missing_items':[{'label':'B','source_quote':'2 desks','room_function':'office',
                                 'category':'desk','min_count':2}], 'missing_functions':[], 'issues':[]}
        with self.assertRaises(ValueError):apply_coverage_review([row],review,row['source_quote'])
        review['missing_items'][0].update(label='A',min_count=1)
        with self.assertRaisesRegex(ValueError,'conflicting counts'):
            apply_coverage_review([row],review,row['source_quote'])
        self.assertEqual(row['inventory'][0]['min_count'],2)

    def test_balanced_four_seats_keep_requested_count_without_integer_slot_bias(self):
        room=Room('r','Dining','living_room',Bounds2D(0,0,5,4))
        programs=list(inventory_programs(room,[{'category':'dining_table','min_count':1},
                                              {'category':'dining_chair','min_count':4}]))
        self.assertEqual(len(programs),2)
        design=programs[0].design;design.validate(ASSET_CATALOG)
        members=design.groups[0]['members']
        self.assertEqual(len(members),4)
        for side in ['front','back']:
            self.assertEqual(sorted(m['slot'] for m in members if m['side']==side),[-.5,.5])
        invalid=deepcopy(design);invalid.groups[0]['members'][0]['slot']=.3
        with self.assertRaises(ValueError):invalid.validate(ASSET_CATALOG)

    def test_floor_capacity_feedback_preserves_source_geometry(self):
        from test_floor_brief import FloorBriefTests
        from cityg.planning.floor_brief import resolve_brief,geometry_summary
        from cityg.planning.floor_inventory_capacity import check_inventory_capacity
        b,base,spec,brief=FloorBriefTests().fixture()
        row={**requirement(),'building_function':b.function,'required_functions':['living_room'],
             'inventory':[{'room_function':'living_room','category':'sofa','min_count':1}]}
        b.metadata['interior_layout_contract']={'requirements':[row]}
        profile=resolve_brief(brief,b,base,spec);geometry=geometry_summary(b,base);before=deepcopy(b)
        with patch('cityg.planning.floor_inventory_capacity.find_inventory_witness',
                   return_value=(None,{'status':'no_reference_witness','tested':2})):
            with self.assertRaisesRegex(ValueError,'Replan counts'):
                check_inventory_capacity(profile,b,geometry,object())
        with patch('cityg.planning.floor_inventory_capacity.find_inventory_witness',
                   return_value=(None,{'status':'no_reference_witness','tested':0})):
            report=check_inventory_capacity(profile,b,geometry,object())
            self.assertEqual(report['status'],'partial_reference_coverage')
            self.assertFalse(report['compiled_verified'])
        self.assertEqual(b,before)
