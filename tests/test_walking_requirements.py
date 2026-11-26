import json
import unittest
from copy import deepcopy
from pathlib import Path

from cityg.agents import RequirementAgent
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.prototype_lab import make_lab
from cityg.planning.prototypes import LayoutPrototypeLibrary
from cityg.requirement_ledger import create_ledger, evaluate_ledger
from cityg.schemas import Bridge, CitySpec, Point2D, River
from cityg.serialization import to_primitive
from cityg.walking_requirements import assess, route_clauses, validate
from test_requirement_agent import FakeService, VALID_SPEC


def crossing_fixture():
    library = LayoutPrototypeLibrary(
        Path(__file__).resolve().parents[1] / "configs/layout_prototypes/v1"
    )
    city, targets = make_lab(library, ["office_open_six_mid_v1", "meeting_six_v1"])
    for _, building, _, _ in targets:
        building.metadata["interior_layout_contract"] = {"source": "new_scene_rectangular_interior_v1"}
    road = city.road_network.segments[0]
    road.sidewalk_width_m = 4
    mid = city.bounds.center.x
    city.rivers = [River("river", "River", (Point2D(mid, 0), Point2D(mid, city.bounds.max_y)), 4, 2, 3)]
    station = mid - road.centerline[0].x
    city.bridges = [Bridge("bridge", road.id, "river", station - 4, station + 4)]
    city.world_program = build_world_program(city, producer="walking_regression", seed=17)
    text = "从A楼的首层开放办公室步行到对岸B楼的首层会议室，经过桥，步行距离不超过100米"
    req = {
        "source_quote": text,
        "start": {"quote": "A楼的首层开放办公室", "building": "A", "level": 0, "space": "open_office"},
        "end": {"quote": "B楼的首层会议室", "building": "B", "level": 0, "space": "meeting_room"},
        "max_distance_m": 100,
        "via_bridge": True,
        "opposite_banks": True,
    }
    bindings = [{"label": name, "building_id": b.id} for name, (_, b, _, _) in zip("AB", targets)]
    return city, bindings, req, to_primitive(GeometryCompiler().compile(city))


class WalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city, cls.bindings, cls.req, cls.manifest = crossing_fixture()

    def check_route(self, req=None, manifest=None):
        return assess(
            self.city, self.bindings, [req or self.req], self.manifest if manifest is None else manifest
        )[0]

    def test_floor_function_without_furniture_or_area(self):
        from cityg.agents.interior_requirement import InteriorRequirementAgent
        from test_interior_requirements import requirement

        text = "建筑A为商业，首层设置会议室"
        row = dict(
            requirement(),
            source_quote=text,
            area_m2=None,
            area_basis=None,
            required_functions=["meeting_room"],
            inventory=[],
        )
        service = FakeService(
            [
                json.dumps({"interior_requirements": [row]}),
                json.dumps(
                    {
                        "missing_items": [
                            {
                                "room_function": "meeting_room",
                                "category": "meeting_table",
                                "min_count": 1,
                                "source_quote": "会议室",
                            }
                        ]
                    }
                ),
            ]
        )
        rows, _ = InteriorRequirementAgent(service, 1).extract(text)
        self.assertEqual(rows[0]["inventory"], [])
        self.assertIsNone(rows[0]["area_m2"])

    def test_route_distance_does_not_become_planar_distance(self):
        from cityg.agents.urban_scope import urban_scope

        service = FakeService(['{"indices":[0,1]}'])
        text = self.req["source_quote"] + "。办公区位于公园北侧。"
        selected, _ = urban_scope(text, service)
        self.assertEqual(selected, ["办公区位于公园北侧。"])

    def test_focused_extraction_keeps_literal_endpoint_phrases(self):
        from cityg.agents.walking_requirement import extract_walks
        text=self.req['source_quote']
        data={k:v for k,v in self.req.items() if k!='source_quote'}
        service=FakeService([json.dumps(data)])
        bindings=[{'label':a,'levels':[0],'required_functions':[f]} for a,f in [('A','open_office'),('B','meeting_room')]]
        rows,trace=extract_walks(service,[text],bindings,2)
        self.assertEqual(rows,[self.req])
        self.assertEqual(len(trace),1)
        schema=service.calls[0][1]['properties']
        self.assertEqual(schema['start']['properties']['building']['enum'],['A'])
        self.assertEqual(schema['end']['properties']['building']['enum'],['B'])

    def test_reader_and_final_ledger(self):
        text = self.req["source_quote"]
        fake = FakeService(
            [json.dumps(VALID_SPEC), json.dumps(dict(VALID_SPEC, river_mode="meandering", walking_requirements=[self.req]))]
        )
        parsed = RequirementAgent(fake, max_attempts=2).parse(text)
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("walking_requirements", fake.calls[0][1]["required"])
        ledger = create_ledger(text, parsed.spec)
        # This fixture tests the route binding independently of interior furniture contracts.
        ledger["bound_interior_requirements"] = []
        req = deepcopy(self.req)
        for side, binding in zip(("start", "end"), self.bindings):
            endpoint = req[side]
            req["source_quote"] = req["source_quote"].replace(
                endpoint["quote"],
                endpoint["quote"].replace(endpoint["building"], binding["building_id"]),
            )
            endpoint["quote"] = endpoint["quote"].replace(endpoint["building"], binding["building_id"])
            endpoint["building"] = binding["building_id"]
        ledger["parsed_spec"]["walking_requirements"] = [req]

        def walk(**kw):
            evaluate_ledger(ledger, self.city, **kw)
            rows = [r for r in ledger["requirements"] if r.get("check") == "compiled_walk"]
            self.assertEqual(len(rows), 1)
            return rows[0]

        self.assertEqual(walk()["status"], "pending")
        self.assertEqual(walk(final=True)["status"], "unverified")
        evidence = walk(compiled_manifest=self.manifest)
        self.assertEqual(evidence["status"], "satisfied", evidence)
        self.assertEqual(evidence["actual"]["bridge_ids"], ["bridge"])
        self.assertEqual(list(map(len, evidence["actual"]["door_ids"])), [2, 2])

    def test_bounded_distance_and_disconnected_surfaces(self):
        self.assertEqual(self.check_route()["status"], "satisfied")
        r = {**self.req, "max_distance_m": 30}
        self.assertEqual(self.check_route(req=r)["status"], "unverified")
        for predicate in (
            lambda p: p["semantic_class"] == "bridge_deck",
            lambda p: p["id"] == "geom_meeting_six_v1_door",
            lambda p: p["semantic_class"] == "frontage_connector",
        ):
            scene = {
                **self.manifest,
                "primitives": [p for p in self.manifest["primitives"] if not predicate(p)],
            }
            self.assertEqual(self.check_route(manifest=scene)["status"], "unverified")

    def test_ledger_audits_destination_even_if_source_door_missing(self):
        scene = {**self.manifest, "primitives": [
            p for p in self.manifest["primitives"] if p["id"] != "geom_office_open_six_mid_v1_door"
        ]}
        row = self.check_route(manifest=scene)
        self.assertEqual(row["status"], "unverified")
        start = row["floor_access"]["start"]["doors"][0]
        self.assertEqual(start["failures"][0]["code"], "missing_or_impassable_portal")
        end = row["floor_access"]["end"]["doors"][0]
        self.assertEqual(end["status"], "verified")
        self.assertGreaterEqual(len(end["polyline_xy_m"]), 2)

    def test_endpoint_binding_and_scope(self):
        r = deepcopy(self.req)
        r["end"]["building"] = "C"
        self.assertEqual(self.check_route(req=r)["status"], "unverified")
        r = {**deepcopy(self.req), "via_bridge": False, "opposite_banks": False}
        r["end"]["space"] = "sidewalk"
        r["end"]["building"] = "A"
        self.assertEqual(self.check_route(req=r)["status"], "satisfied")
        self.assertEqual(route_clauses("Connect buildings to a pedestrian-friendly street network."), [])
        for key, value in [("opposite_banks", False), ("via_bridge", False), ("max_distance_m", 1)]:
            with self.assertRaises(ValueError):
                validate([{**self.req, key: value}], self.req["source_quote"])
        r = deepcopy(self.req)
        r["end"]["space"] = "entrance"
        with self.assertRaises(ValueError):
            validate([r], r["source_quote"])


if __name__ == "__main__":
    unittest.main()
