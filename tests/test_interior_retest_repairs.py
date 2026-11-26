"""Regressions exposed by the paired N30 area/inventory retest."""
import json
import random
import unittest
from copy import deepcopy
from cityg.agents import RequirementAgent
from cityg.interior_requirements import validate_requirements
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import Bounds2D
from test_requirement_agent import FakeService, VALID_SPEC
from test_interior_requirements import requirement

class InteriorRetestRepairsTests(unittest.TestCase):
    def test_requirement_retry_explains_actual_function_choices(self):
        bad=requirement();bad['required_functions']=['restaurant'];bad['inventory']=[]
        with self.assertRaisesRegex(ValueError,'break_room'):
            validate_requirements([bad])

    def test_repeated_schema_failure_uses_final_bounded_plain_json_attempt(self):
        invalid=deepcopy(VALID_SPEC);invalid['building_count']=10**100
        service=FakeService([json.dumps(invalid),json.dumps(invalid),json.dumps(VALID_SPEC)])
        result=RequirementAgent(service,max_attempts=3).parse('make a district')
        self.assertEqual(len(result.attempts),3)
        self.assertIsNone(service.calls[2][1])
        self.assertIn('schema',service.calls[2][0][-1].content)

    def test_truncation_switches_next_attempt_without_replaying_repetitive_output(self):
        from types import SimpleNamespace
        class Service:
            def __init__(self): self.calls=[]
            def complete_with_metadata(self, messages, schema):
                self.calls.append((list(messages),schema))
                return SimpleNamespace(content=('REPETITIVE_OUTPUT '*500 if len(self.calls)==1 else json.dumps(VALID_SPEC)),
                    finish_reason=('length' if len(self.calls)==1 else 'stop'),usage={})
        service=Service()
        result=RequirementAgent(service,max_attempts=3).parse('make a district')
        self.assertEqual(len(result.attempts),2)
        self.assertIsNone(service.calls[1][1])
        self.assertTrue(all('REPETITIVE_OUTPUT' not in m.content for m in service.calls[1][0]))
        self.assertIn('REPETITIVE_OUTPUT',result.attempts[0].raw_output)

    def test_missing_carrier_zone_is_replanned_before_building_binding(self):
        bad=deepcopy(VALID_SPEC);bad['zones']=[bad['zones'][0]]
        bad['interior_requirements']=[requirement()]
        fixed=deepcopy(VALID_SPEC);fixed['interior_requirements']=[requirement()]
        service=FakeService([json.dumps(bad),json.dumps(fixed)])
        result=RequirementAgent(service).parse(requirement()['source_quote'])
        self.assertEqual(len(result.attempts),2)
        self.assertIn('carrier',result.attempts[0].error)

    def test_subdivision_has_buildable_width_and_real_street_access(self):
        block=Bounds2D(0,0,50,50)
        for count in [2,3,4]:
            sites=BaselineCityPlanner._subdivide_block(block,'block',count,random.Random(17),
                preferred_side='north',minimum_site_span=18)
            self.assertEqual(len(sites),count)
            self.assertAlmostEqual(sum(s.bounds.area for s in sites),block.area)
            for s in sites:
                self.assertGreaterEqual(min(s.bounds.width,s.bounds.depth),18-1e-8)
                for front in s.frontage_sides:
                    self.assertEqual(getattr(s.bounds,{'west':'min_x','east':'max_x','south':'min_y','north':'max_y'}[front]),
                                     getattr(block,{'west':'min_x','east':'max_x','south':'min_y','north':'max_y'}[front]))
                for t in sites:
                    if t is not s:
                        overlap_x=max(0,min(s.bounds.max_x,t.bounds.max_x)-max(s.bounds.min_x,t.bounds.min_x))
                        overlap_y=max(0,min(s.bounds.max_y,t.bounds.max_y)-max(s.bounds.min_y,t.bounds.min_y))
                        self.assertAlmostEqual(overlap_x*overlap_y,0)
        with self.assertRaisesRegex(ValueError,'revise urban density'):
            BaselineCityPlanner._subdivide_block(Bounds2D(0,0,20,20),'block',4,random.Random(17),minimum_site_span=18)

class InventoryEvidenceTests(unittest.TestCase):
    def test_schema_quotes_are_literal_and_only_exact_duplicate_predicates_collapse(self):
        from cityg.agents.requirement import CITY_SPEC_RESPONSE_SCHEMA
        from cityg.interior_requirements import response_schema
        from cityg.inventory_provenance import ground_extraction_schema, deduplicate_identical_inventory
        schema=deepcopy(CITY_SPEC_RESPONSE_SCHEMA)
        schema['properties']['interior_requirements']=response_schema()
        text='Build a city. Building A needs an office. Building B needs a home.'
        grounded=ground_extraction_schema(schema,text)
        quotes=grounded['properties']['interior_requirements']['items']['properties']['source_quote']['enum']
        self.assertTrue(all(q in text for q in quotes))
        self.assertIn('Building A needs an office.',quotes)
        self.assertNotIn('enum',schema['properties']['interior_requirements']['items']['properties']['source_quote'])
        one={'room_function':'living_room','category':'sofa','min_count':1}
        conflict={**one,'min_count':2}
        source={'interior_requirements':[{'inventory':[one,one,conflict]}]}
        normalized=deduplicate_identical_inventory(source)
        self.assertEqual(normalized['interior_requirements'][0]['inventory'],[one,conflict])
        self.assertEqual(len(source['interior_requirements'][0]['inventory']),3)

    def test_numeric_evidence_does_not_invent_counts(self):
        from cityg.inventory_provenance import validate_inventory_source
        def check(q,n,basis='explicit_number'):
            return validate_inventory_source({'source_quote':q,'min_count':n,'count_basis':basis},q)
        check('seating for six',6)
        check('四把椅子',4)
        check('one hundred and twenty six chairs',126)
        check('二十五张桌子',25)
        check('customer tables with chairs',1,'presence')
        for q,n,b in [('customer tables with chairs',4,'presence'),('seating for six',16,'explicit_number'),
                      ('twenty-six chairs',6,'explicit_number'),('二十五把椅子',5,'explicit_number')]:
            with self.assertRaises(ValueError):check(q,n,b)

    def test_two_living_rooms_share_complete_bundles(self):
        from types import SimpleNamespace
        from cityg.refinement.inventory_allocation import allocate_remaining_inventory
        from cityg.schemas import Room, Floor
        rooms=[Room(f'r{i}','living','living_room',Bounds2D(i*5,0,i*5+4,6)) for i in range(2)]
        inventory=[{'room_function':'living_room','category':c,'min_count':n} for c,n in
                   [('sofa',1),('coffee_table',1),('dining_table',1),('dining_chair',4)]]
        b=SimpleNamespace(metadata={'interior_layout_contract':{'requirements':[{'levels':[0],'inventory':inventory}]}})
        floor=Floor('f',0,0,3,rooms=rooms)
        allocation=allocate_remaining_inventory(b,floor,'living_room')
        self.assertEqual(len(allocation),2)
        groups=[{i['category'] for i in items} for items in allocation.values()]
        self.assertIn({'sofa','coffee_table'},groups);self.assertIn({'dining_table','dining_chair'},groups)
        for rid,items in allocation.items():
            floor.objects.extend(SimpleNamespace(room_id=rid,category=i['category']) for i in items for _ in range(i['min_count']))
            rest=allocate_remaining_inventory(b,floor,'living_room',excluded=[rid])
            self.assertEqual(len(rest),1)
            self.assertFalse({i['category'] for i in items}&{i['category'] for v in rest.values() for i in v})
            break
