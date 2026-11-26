import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from cityg.agent_pipeline import AgenticGenerationPipeline
from cityg.agents import AgentGenerationError, RequirementAgent


VALID_SPEC = {
    "name": "agent_test",
    "width_m": 320,
    "depth_m": 260,
    "building_count": 8,
    "min_floors": 2,
    "max_floors": 4,
    "rooms_per_floor": 5,
    "road_width_m": 12,
    "sidewalk_width_m": 2.5,
    "parcel_setback_m": 4,
    "seed": 11,
    "zones": [
        {"name": "homes", "function": "residential", "weight": 0.7},
        {"name": "shops", "function": "commercial", "weight": 0.3},
    ],
}


class FakeService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, response_schema=None):
        self.calls.append((messages, response_schema))
        return self.responses.pop(0)


class RequirementAgentTests(unittest.TestCase):
    def test_separate_interior_extraction_keeps_urban_contract_prompt(self):
        service = FakeService([json.dumps(VALID_SPEC)])
        with patch('cityg.agents.interior_requirement.InteriorRequirementAgent.extract',
                   return_value=([], ())):
            RequirementAgent(service, separate_interiors=True).parse('homes north of shops')
        prompt = service.calls[0][0][0].content
        self.assertIn('Preserve urban spatial demands', prompt)
        self.assertIn('min_footprint_area', prompt)
        self.assertIn('urban_requirements', service.calls[0][1]['required'])

    def test_exterior_default_ratio_and_explicit_override(self):
        result = RequirementAgent(FakeService([json.dumps(VALID_SPEC)]), exterior_only=True).parse('outdoor city')
        self.assertEqual(result.spec.architecture['expressive_ratio'], .2)
        source = dict(VALID_SPEC, architecture={'expressive_ratio': .5})
        result = RequirementAgent(FakeService([json.dumps(source)]), exterior_only=True).parse('half expressive buildings')
        self.assertEqual(result.spec.architecture['expressive_ratio'], .5)
        result = RequirementAgent(FakeService([json.dumps(VALID_SPEC)])).parse('indoor city')
        self.assertNotIn('expressive_ratio', result.spec.architecture)

    def test_valid_spec_is_accepted_and_traced(self):
        service = FakeService([json.dumps(VALID_SPEC)])
        result = RequirementAgent(service, model_id="fake").parse("make a district")
        self.assertEqual(result.spec.building_count, 8)
        self.assertEqual(result.model_id, "fake")
        self.assertEqual(len(result.attempts), 1)
        self.assertIsNone(result.attempts[0].error)
        self.assertEqual(service.calls[0][1]["type"], "object")

    def test_invalid_candidate_is_retried_with_validator_feedback(self):
        invalid = dict(VALID_SPEC, building_count=10**100)
        service = FakeService([json.dumps(invalid), json.dumps(VALID_SPEC)])
        result = RequirementAgent(service, max_attempts=2).parse("make a district")
        self.assertEqual(len(result.attempts), 2)
        self.assertIn("building_count", result.attempts[0].error)
        self.assertIn("rejected", service.calls[1][0][-1].content)

    def test_retry_budget_is_enforced(self):
        service = FakeService(["not json", "still not json"])
        with self.assertRaises(AgentGenerationError) as context:
            RequirementAgent(service, max_attempts=2).parse("make a district")
        self.assertEqual(len(context.exception.attempts), 2)

    def test_pipeline_writes_spec_trace_and_valid_city(self):
        service = FakeService([json.dumps(VALID_SPEC)])
        pipeline = AgenticGenerationPipeline(RequirementAgent(service, model_id="fake"))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = pipeline.run("make a district", output)
            self.assertTrue(result.ok)
            self.assertTrue((output / "requested_spec.json").is_file())
            self.assertTrue((output / "requirement_trace.json").is_file())
            self.assertTrue((output / "city.json").is_file())


if __name__ == "__main__":
    unittest.main()
