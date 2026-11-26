import copy
import json
import unittest
from pathlib import Path

from cityg.agents import RequirementAgent, AgentGenerationError
from cityg.agents.requirement_contracts import explicit_contract, check_explicit_contract, constrained_response_schema
from cityg.agents.requirement import CITY_SPEC_RESPONSE_SCHEMA
from cityg.architecture import make_appearance_plan, merge_architecture
from cityg.morphology import contract_issues, realization_report
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec, Point2D
from cityg.serialization import to_primitive, city_from_dict
from cityg.validation import CityValidator


class MorphologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((Path(__file__).parents[1]/'examples/morphology_showcase.json').read_text())
        cls.spec = CitySpec.from_dict(cls.source)
        cls.city = BaselineCityPlanner().plan(cls.spec)

    def test_realized_visible_roads_river_and_envelopes(self):
        report = realization_report(self.city)
        self.assertGreater(report['visibly_curved_road_count'], 0)
        self.assertGreater(report['straight_road_length_ratio'], .65)
        self.assertGreater(report['junction_degree_counts'].get('3', 0), 0)
        self.assertGreater(report['rivers']['river_000']['max_deviation_m'], 50)
        self.assertEqual(report['exterior_shape_counts'],
                         {'legacy_archetype': 4, 'rectangle': 2, 'ellipse': 2, 'chamfered': 2, 'hexagon': 2})
        self.assertFalse(contract_issues(self.city))
        validation = CityValidator().validate(self.city)
        self.assertTrue(validation.ok, validation.to_dict())

    def test_contract_detects_regression_and_roundtrips(self):
        city = city_from_dict(to_primitive(self.city))
        self.assertFalse(contract_issues(city))
        for r in city.road_network.segments:
            r.centerline = (r.centerline[0], r.centerline[-1])
        river = city.rivers[0]
        river.centerline = (river.centerline[0], river.centerline[-1])
        bid = next(iter(city.metadata['morphology_contract']['building_envelopes']))
        next(b for b in city.iter_buildings() if b.id == bid).metadata['appearance_plan']['envelope'] = {}
        self.assertEqual({x[0] for x in contract_issues(city)}, {'roads', 'river', bid})

    def test_boundaries_and_independent_straight_streets(self):
        city = self.city
        for road in city.road_network.segments:
            for p in road.centerline:
                self.assertTrue(0 <= p.x <= self.spec.width_m)
                self.assertTrue(0 <= p.y <= self.spec.depth_m)
        # A curved river does not impose a shared deformation on all collectors.
        vertical = [r for r in city.road_network.segments if len(r.centerline) == 2
                    and r.centerline[0].x == r.centerline[-1].x]
        self.assertGreater(len(vertical), 8)
        self.assertLess(len(city.bridges), len({j.position.y for j in city.road_network.junctions}))

    def test_palette_precedence_and_determinism(self):
        a = {'envelope': {'shape': 'ellipse'}}
        b = {'envelope_palette': [{'shape': 'rectangle'}, {'shape': 'hexagon'}]}
        context = merge_architecture(a, b)
        building = next(self.city.iter_buildings())
        self.assertEqual([make_appearance_plan(building, context, ordinal=i)['envelope']['shape']
                          for i in range(4)], ['rectangle', 'hexagon', 'rectangle', 'hexagon'])
        self.assertNotIn('envelope_palette', merge_architecture(b, a))

    def test_schema_rejects_unsafe_or_unused_intent(self):
        for value in ({'road_warp_ratio': .5}, {'river_cycles': float('nan')}, {'unknown': 1}):
            with self.assertRaises(ValueError):
                CitySpec(road_pattern='landscape_adaptive', morphology=value).validate()
        with self.assertRaises(ValueError):
            CitySpec(morphology={'road_warp_ratio': .02}).validate()

    def test_explicit_requirements_retry_on_missing_envelope(self):
        source = copy.deepcopy(self.source)
        bad = copy.deepcopy(source)
        del bad['zones'][1]['architecture']['envelope_palette']
        class Service:
            def __init__(self): self.responses = [bad, source]
            def complete(self, *args): return json.dumps(self.responses.pop(0))
        result = RequirementAgent(Service()).parse('Only exterior. Use this spec: '+json.dumps(source))
        self.assertEqual(len(result.attempts), 2)
        self.assertIn('envelope_palette', result.attempts[0].error)

    def test_numbered_and_qualified_assignments(self):
        text = ('2. Waterfront architecture={"envelope":{"shape":"ellipse"}}\n'
                'zones[1].architecture.envelope={"shape":"ellipse"}')
        contract = explicit_contract(text)
        actual = {'zones': [{}, {'architecture': {'envelope': {'shape': 'ellipse', 'profile': 'straight'}}}]}
        check_explicit_contract(actual, contract)
        actual['zones'][1]['architecture']['envelope']['shape'] = 'rectangle'
        with self.assertRaises(ValueError):
            check_explicit_contract(actual, contract)

    def test_guided_schema_preserves_original_and_requires_explicit_fields(self):
        original = copy.deepcopy(CITY_SPEC_RESPONSE_SCHEMA)
        contract = explicit_contract('Use this '+json.dumps(self.source))
        schema = constrained_response_schema(original, contract)
        self.assertEqual(original, CITY_SPEC_RESPONSE_SCHEMA)
        self.assertIn('morphology', schema['required'])
        self.assertEqual(schema['properties']['road_pattern']['const'], 'landscape_adaptive')
        variants = schema['properties']['zones']['items']['anyOf']
        self.assertIn('envelope_palette', variants[1]['properties']['architecture']['required'])

    def test_explicit_scalar_and_conflicting_assignments(self):
        c = explicit_contract('road_pattern=landscape_adaptive，building_count=12。')
        self.assertEqual(c, {'road_pattern': 'landscape_adaptive', 'building_count': 12})
        text = 'architecture={"envelope":{"shape":"ellipse"}}\narchitecture.envelope={"shape":"hexagon"}'
        with self.assertRaises(ValueError):
            constrained_response_schema(CITY_SPEC_RESPONSE_SCHEMA, explicit_contract(text))


if __name__ == '__main__':
    unittest.main()
