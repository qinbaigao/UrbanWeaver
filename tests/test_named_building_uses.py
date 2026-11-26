import unittest
from cityg.agents.building_uses import ground_named_uses, named_building_uses
from cityg.interior_requirements import evaluate_requirements
from tests.test_interior_requirements import fixture, requirement


class NamedBuildingUsesTests(unittest.TestCase):
    def test_city_mix_does_not_override_explicit_individual_uses(self):
        text = ('Create a mixed-use quarter. Detail residential building A and commercial building B. '
                'Building A needs a living room. Building B needs a shop.')
        rows = [{'label':'A', 'building_function':'mixed_use'}, {'label':'Building B', 'building_function':'mixed_use'}]
        ground_named_uses(rows,text)
        self.assertEqual([r['building_function'] for r in rows], ['residential','commercial'])
        self.assertEqual(named_building_uses(text)['A']['quote'],'residential building A')

    def test_supported_chinese_and_conflicting_or_conditional_uses(self):
        text='设计一个混合用途社区。A栋为住宅，建筑B用作办公。'
        self.assertEqual({k:v['function'] for k,v in named_building_uses(text).items()},
                         {'A':'residential','B':'commercial'})
        for text in ('Building A is residential or commercial.', 'Building A is not residential.',
                     'If residential building A is requested, add bedrooms.',
                     'Building A is residential. Building A is commercial.'):
            self.assertEqual(named_building_uses(text),{})

    def test_independent_acceptance_sees_disagreement_even_when_ledger_matches_scene(self):
        city,buildings,_=fixture()
        b=buildings[0]
        row={**requirement(),'building_id':b.id,'building_function':b.function,
             'required_functions':[],'inventory':[],'area_m2':None}
        report,=evaluate_requirements(city,[row],instruction='Detail residential building A.')
        self.assertEqual(report['expected_building_function'],'residential')
        self.assertNotEqual(report['actual_building_function'],'residential')
        self.assertEqual(report['status'],'violated')
