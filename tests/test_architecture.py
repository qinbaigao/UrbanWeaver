import copy
import json
import unittest

from cityg.architecture import DESIGN_LANGUAGES, make_appearance_plan, is_expressive_envelope
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.appearance import bay_tangent, facade_style_for_face, facade_material_style
from cityg.geometry.facades import RESIDENTIAL_FACADE
from cityg.observation import AdaptiveObservationPlanner
from cityg.planning import BaselineCityPlanner
from cityg.planning.programs import BuildingProfile
from cityg.refinement.building import BuildingRefinementPlan, apply_building_refinement
from cityg.schemas import CitySpec, ZoneSpec
from cityg.serialization import to_primitive, city_from_dict
from cityg.validation import CityValidator


class ArchitectureTests(unittest.TestCase):
    def test_expressive_budget_preserves_ordinary_groups(self):
        b = copy.deepcopy(next(self.city.iter_buildings()))
        b.metadata['semantic_envelope_preference'] = {'shape': 'ellipse', 'profile': 'straight'}
        plans = [make_appearance_plan(b, {'expressive_ratio': .2}, ordinal=i % 7, form_ordinal=i)
                 for i in range(100)]
        self.assertEqual(sum(is_expressive_envelope(p['envelope']) for p in plans), 20)
        self.assertEqual(sum(not p['envelope'] for p in plans), 80)
        for ratio, expected in ((0, 0), (.35, 35), (1, 100)):
            self.assertEqual(sum(is_expressive_envelope(make_appearance_plan(
                b, {'expressive_ratio': ratio}, ordinal=i)['envelope']) for i in range(100)), expected)
        # Explicit shape requests override the ordinary-scene budget.
        for context in ({'envelope': {'shape': 'hexagon'}},
                        {'envelope_palette': [{'shape': 'ellipse'}]}):
            self.assertTrue(is_expressive_envelope(make_appearance_plan(
                b, {'expressive_ratio': 0, **context})['envelope']))
        b.metadata.pop('semantic_envelope_preference')
        self.assertFalse(make_appearance_plan(b, {})['envelope'])  # interior legacy unaffected
        self.assertEqual(sum(is_expressive_envelope(make_appearance_plan(
            b, {'expressive_ratio': .2}, ordinal=i)['envelope']) for i in range(100)), 20)

    def test_expressive_ratio_rejects_invalid_values(self):
        for value in (-.1, 1.1, float('nan'), True, '0.2'):
            with self.assertRaises(ValueError):
                CitySpec(architecture={'expressive_ratio': value}).validate()
        self.assertFalse(is_expressive_envelope({'shape': 'rectangle', 'profile': 'taper', 'top_scale': 1}))
        self.assertFalse(is_expressive_envelope({'shape': 'rectangle', 'profile': 'lean', 'lean_x': 0, 'lean_y': 0}))
        self.assertTrue(is_expressive_envelope({'shape': 'rectangle', 'profile': 'taper'}))

    @classmethod
    def setUpClass(cls):
        cls.spec = CitySpec(name="appearance_test", width_m=160, depth_m=160,
            building_count=1, min_floors=3, max_floors=3, rooms_per_floor=2,
            seed=17, zones=(ZoneSpec("homes", "residential"),),
            architecture={"region": "user reference", "era": "mixed generations",
                          "design_languages": list(DESIGN_LANGUAGES)})
        cls.city = BaselineCityPlanner().plan(cls.spec)

    def test_context_roundtrip_and_validation(self):
        restored = CitySpec.from_dict(to_primitive(self.spec))
        self.assertEqual(restored, self.spec)
        city = city_from_dict(json.loads(json.dumps(to_primitive(self.city))))
        self.assertEqual(next(city.iter_buildings()).metadata["appearance_plan"],
                         next(self.city.iter_buildings()).metadata["appearance_plan"])
        for bad in ({"country": "X"}, {"design_languages": ["invented"]},
                    {"design_languages": "solid_punched"}, {"era": 123}):
            with self.assertRaises(ValueError):
                CitySpec(architecture=bad).validate()

    def test_zone_override_and_balanced_replay(self):
        spec = CitySpec(name="district_styles", width_m=300, depth_m=300,
            building_count=6, min_floors=2, max_floors=2, rooms_per_floor=2,
            architecture={"region": "shared region", "design_languages": ["framed_grid"]},
            zones=(ZoneSpec("old", "residential", 1, {
                "era": "older", "design_languages": ["paired_windows", "solid_punched"]}),
                   ZoneSpec("new", "residential", 1, {"era": "new"})))
        city = BaselineCityPlanner().plan(spec)
        plans = [b.metadata["appearance_plan"] for b in city.iter_buildings()]
        self.assertEqual(set(p["language"] for p in plans[:3]), {"paired_windows", "solid_punched"})
        self.assertEqual(set(p["language"] for p in plans[3:]), {"framed_grid"})
        self.assertTrue(all(p["context"]["region"] == "shared region" for p in plans))
        self.assertEqual(plans, [b.metadata["appearance_plan"]
                               for b in BaselineCityPlanner().plan(spec).iter_buildings()])
        self.assertGreater(len({p["module_variant"] for p in plans}), 1)

    def test_agent_profile_palette_is_consumed(self):
        profile = BuildingProfile.from_dict(dict(function="residential", floor_policy="varied",
            entrance_side="west", prototype_id="residential_slab",
            design_language_palette=["shaded_bays"]))
        b = copy.deepcopy(next(self.city.iter_buildings()))
        b.metadata["semantic_design_language_palette"] = list(profile.design_language_palette)
        self.assertEqual(make_appearance_plan(b, {})["language"], "shaded_bays")

    def test_six_languages_change_geometry_not_collision_or_navigation(self):
        signatures = set()
        collision_reference = navigation_reference = None
        for language in DESIGN_LANGUAGES:
            city = copy.deepcopy(self.city)
            b = next(city.iter_buildings())
            b.metadata["appearance_plan"]["language"] = language
            scene = GeometryCompiler(include_interiors=False).compile(city)
            report = GeometryValidator().validate(city, scene)
            self.assertTrue(report.ok, report.to_dict())
            details = [p for p in scene.primitives if p.metadata.get("design_language")]
            self.assertTrue(details)
            self.assertTrue(all(not p.collision_enabled for p in details))
            # Ignore IDs/materials/metadata: prove real geometry differences.
            signature = sorted((p.semantic_class, tuple(to_primitive(p.center).values()),
                                tuple(to_primitive(p.size).values())) for p in details)
            signatures.add(json.dumps(signature))
            collisions = [to_primitive(p) for p in scene.primitives if p.collision_enabled]
            navigation = to_primitive(scene.navigation)
            if collision_reference is None:
                collision_reference, navigation_reference = collisions, navigation
            self.assertEqual(collisions, collision_reference)
            self.assertEqual(navigation, navigation_reference)
            anchor = scene.metadata["facade_buildings"][b.id]["entrance_anchor"]
            doors = [p for p in details if p.metadata.get("entrance_anchor_id") == anchor["id"]]
            self.assertTrue(doors)
            self.assertTrue(all(p.metadata["entrance_anchor_tangent_m"] == anchor["tangent_m"] for p in doors))
        self.assertEqual(len(signatures), 6)

    def test_primary_service_and_pair_spacing(self):
        b = copy.deepcopy(next(self.city.iter_buildings()))
        b.metadata["entrance_side"] = "west"
        b.metadata["appearance_plan"]["language"] = "paired_windows"
        primary = facade_style_for_face(b, RESIDENTIAL_FACADE, "west")
        service = facade_style_for_face(b, RESIDENTIAL_FACADE, "east")
        self.assertGreater(service.bay_width_m, primary.bay_width_m)
        self.assertLess(service.window_ratio, primary.window_ratio)
        values = [bay_tangent(b, 0, 3, i, 5) for i in range(5)]
        self.assertLess(values[1] - values[0], values[2] - values[1])
        self.assertEqual(values[-1], 13.5)

    def test_refinement_transaction_and_context_gate(self):
        b = next(self.city.iter_buildings())
        result = apply_building_refinement(self.city, BuildingRefinementPlan(
            b.id, "visible facade rhythm feedback", {"design_language": "vertical_piers"}))
        self.assertTrue(result.validation.ok)
        updated = next(result.city.iter_buildings())
        self.assertEqual(updated.metadata["appearance_plan"]["language"], "vertical_piers")
        self.assertEqual(updated.metadata["appearance_plan"]["context"], b.metadata["appearance_plan"]["context"])
        restricted = copy.deepcopy(b)
        restricted.metadata["appearance_plan"]["allowed_languages"] = ["solid_punched"]
        with self.assertRaises(ValueError):
            BuildingRefinementPlan(b.id, "bad", {"design_language": "vertical_piers"}).validate(restricted)
        bad = copy.deepcopy(self.city)
        next(bad.iter_buildings()).metadata["appearance_plan"]["language"] = "invented"
        self.assertFalse(CityValidator().validate(bad).ok)

    def test_observation_carries_architectural_intent(self):
        views = AdaptiveObservationPlanner(include_room_views=False)._building_views(self.city, [])
        self.assertTrue(views)
        self.assertTrue(all(v.semantic_context.get("appearance_plan") for v in views))

    def test_legacy_building_keeps_original_style(self):
        b = copy.deepcopy(next(self.city.iter_buildings()))
        b.metadata.pop("appearance_plan")
        self.assertIs(facade_style_for_face(b, RESIDENTIAL_FACADE, "west"), RESIDENTIAL_FACADE)

    def test_material_intent_changes_shell_and_rejects_out_of_palette(self):
        b = copy.deepcopy(next(self.city.iter_buildings()))
        b.metadata["appearance_plan"] = make_appearance_plan(b, {"material_palette": ["brick"]})
        self.assertEqual(facade_material_style(b, RESIDENTIAL_FACADE).wall_material, "residential_brick")
        b.metadata["appearance_plan"]["material_family"] = "glass"
        with self.assertRaises(ValueError):
            facade_material_style(b, RESIDENTIAL_FACADE)

    def test_module_selector_uses_individual_building_key(self):
        from cityg.facade_runtime import FacadeAssetRuntime
        from unittest.mock import Mock
        runtime = object.__new__(FacadeAssetRuntime)
        runtime._ranked_records = Mock(return_value=[])
        b = copy.deepcopy(next(self.city.iter_buildings()))
        runtime.plan_for_building(b, zones=["podium"])
        first = runtime._ranked_records.call_args.kwargs["building_id"]
        b.id = "another_building_same_function"
        runtime.plan_for_building(b, zones=["podium"])
        second = runtime._ranked_records.call_args.kwargs["building_id"]
        self.assertNotEqual(first, second)

    def test_exterior_camera_observes_entrance_side(self):
        import math
        b = next(self.city.iter_buildings())
        v = AdaptiveObservationPlanner(include_room_views=False)._building_views(self.city, [])[0]
        side_angle = {"east": 0, "north": 90, "west": 180, "south": 270}[b.metadata["entrance_side"]]
        angle = math.radians(side_angle + b.metadata.get("orientation_deg", 0))
        offset = (v.camera_position[0] - b.footprint.center.x,
                  v.camera_position[1] - b.footprint.center.y)
        self.assertGreater(offset[0] * math.cos(angle) + offset[1] * math.sin(angle), 0)


if __name__ == "__main__":
    unittest.main()
