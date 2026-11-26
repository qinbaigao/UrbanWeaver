import json
import unittest

from cityg.agents import AgentGenerationError, RepairAgent
from cityg.evaluation import inject_error
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.validation import CityValidator, ValidationReport


class FakeService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, response_schema=None):
        self.calls.append((messages, response_schema))
        return self.responses.pop(0)


class RepairAgentTests(unittest.TestCase):
    def setUp(self):
        self.valid = BaselineCityPlanner().plan(
            CitySpec(
                name="agent_repair",
                width_m=180,
                depth_m=160,
                building_count=2,
                min_floors=2,
                max_floors=2,
                rooms_per_floor=3,
            )
        )
        self.invalid = inject_error(self.valid, "disconnected_entrance")

    def _proposal(self):
        building = next(self.valid.iter_buildings())
        relation = next(
            item
            for item in self.valid.world_program.relations
            if item.id == f"rel_building_access__{building.id}"
        )
        return json.dumps(
            {
                "reason": "restore the contract-required access relation",
                "operations": [
                    {
                        "op": "add_relation",
                        "target_id": building.id,
                        "path": "",
                        "value_json": json.dumps(to_primitive(relation)),
                    }
                ],
            }
        )

    def test_valid_local_patch_is_applied(self):
        service = FakeService([self._proposal()])
        result = RepairAgent(service, model_id="fake").repair(self.invalid)
        self.assertTrue(result.validation.ok)
        self.assertEqual(result.touched_entity_ids, ("building_000",))
        self.assertEqual(result.patch.scope_entity_id, "building_000")
        self.assertEqual(result.patch.expected_versions, {"building_000": 1})
        self.assertEqual(len(result.attempts), 1)

    def test_out_of_scope_patch_is_retried_then_fails(self):
        invalid_proposal = json.dumps(
            {
                "reason": "bad",
                "operations": [
                    {
                        "op": "replace_entity",
                        "target_id": "building_001",
                        "path": "name",
                        "value_json": json.dumps("forbidden"),
                    }
                ],
            }
        )
        service = FakeService([invalid_proposal, invalid_proposal])
        with self.assertRaises(AgentGenerationError) as context:
            RepairAgent(service, max_attempts=2).repair(self.invalid)
        self.assertEqual(len(context.exception.attempts), 2)
        self.assertIn("scope_violation", context.exception.attempts[0].error)

    def test_already_valid_city_is_not_sent_to_model(self):
        service = FakeService([])
        with self.assertRaisesRegex(ValueError, "already passes"):
            RepairAgent(service).repair(self.valid, CityValidator().validate(self.valid))
        self.assertFalse(service.calls)

    def test_nested_scopes_use_intersection_and_fix_canonical_door(self):
        broken=inject_error(self.valid,'disconnected_room')
        floor=next(self.valid.iter_floors())
        door=next(d for d in floor.doors if d.room_b_id is not None)
        proposal=json.dumps({'reason':'restore endpoint','operations':[{
            'op':'replace_entity','target_id':door.id,'path':'room_b_id',
            'value_json':json.dumps(door.room_b_id)}]})
        result=RepairAgent(FakeService([proposal])).repair(broken)
        self.assertTrue(result.validation.ok)
        self.assertEqual(result.patch.scope_entity_id,floor.id)
        self.assertEqual(next(broken.iter_floors()).doors[0].room_b_id,None)

    def test_disjoint_or_missing_scopes_never_expand_to_city(self):
        for scopes in (['building_000','building_001'],['building_000',None]):
            report=ValidationReport()
            for s in scopes: report.add('error','test','test',s,allowed_patch_scope=s)
            service=FakeService([])
            with self.assertRaises(ValueError): RepairAgent(service).repair(self.valid,report)
            self.assertFalse(service.calls)

    def test_geometry_value_cannot_be_smuggled_as_relation(self):
        proposal={'reason':'wrong op','operations':[{'op':'add_relation','target_id':'building_000',
                  'path':'bounds','value_json':'{"min_x":0}'}]}
        with self.assertRaisesRegex(ValueError,'replace_entity'):
            RepairAgent(FakeService([]))._make_patch(self.valid,'building_000',proposal,1)


if __name__ == "__main__":
    unittest.main()
