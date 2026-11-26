import unittest
import math

from cityg.observation import AdaptiveObservationPlanner, fit_capture_view
from cityg.adaptive_review import _local_recheck_plan
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec, InteriorObject, Point2D


class ObservationPlannerTests(unittest.TestCase):
    def test_top_down_capture_fits_portrait_canvas_and_high_furniture(self):
        view={'kind':'room_interior','camera_position':[4,3,9], 'look_at':[4,3,0],
              'up':[0,1,0],'fov_deg':50,
              'semantic_context':{'top_down_audit_bounds_world':[0,0,0,8,6,3]}}
        fitted=fit_capture_view(view,width=600,height=736)
        distance=fitted['camera_position'][2]-3
        vertical=2*distance*math.tan(math.radians(25))
        self.assertGreaterEqual(vertical,6*1.08)
        self.assertGreaterEqual(vertical*(600/736),8*1.08)
        self.assertEqual(view['camera_position'],[4,3,9])
        self.assertEqual(fitted['look_at'],view['look_at'])
        landscape=fit_capture_view(view,width=1200,height=736)
        self.assertLess(landscape['camera_position'][2],fitted['camera_position'][2])
        perspective={**view,'camera_position':[1,1,2]}
        self.assertEqual(fit_capture_view(perspective,width=600,height=736),perspective)

    def setUp(self):
        self.city = BaselineCityPlanner().plan(
            CitySpec(
                name="observation_test",
                width_m=180,
                depth_m=160,
                building_count=4,
                min_floors=2,
                max_floors=4,
                rooms_per_floor=4,
                seed=19,
            )
        )

    def test_plan_is_bounded_and_contains_global_views(self):
        plan = AdaptiveObservationPlanner(max_views=8).plan(self.city)
        self.assertLessEqual(len(plan.selected_views), 8)
        self.assertGreaterEqual(
            sum(view.kind == "global" for view in plan.selected_views), 2
        )
        self.assertEqual(len(plan.selected_views), len({view.view_id for view in plan.selected_views}))
        self.assertTrue(plan.covered_entity_ids)

    def test_building_exterior_views_never_materialize_full_city_interiors(self):
        plan = AdaptiveObservationPlanner(max_views=8).plan(self.city)
        exterior = [
            view for view in plan.candidates if view.kind == "building_exterior"
        ]
        self.assertTrue(exterior)
        self.assertEqual({view.mode for view in exterior}, {"overview"})

    def test_risk_entity_is_prioritized_and_reported_if_uncovered(self):
        road_id = self.city.road_network.segments[0].id
        plan = AdaptiveObservationPlanner(max_views=3).plan(
            self.city, risk_entity_ids=[road_id]
        )
        self.assertIn(road_id, plan.covered_entity_ids)
        self.assertFalse(plan.uncovered_risk_entity_ids)

    def test_road_views_are_street_archetype_aware_and_bind_adjacent_buildings(self):
        plan = AdaptiveObservationPlanner(max_views=12).plan(self.city)
        road_views = [view for view in plan.candidates if view.kind == "road" and "_road_" in view.view_id]
        self.assertTrue(road_views)
        self.assertTrue(all(view.novelty_key.startswith("street_archetype_") for view in road_views))
        self.assertTrue(all(view.semantic_context.get("street_archetype") for view in road_views))
        self.assertTrue(any(len(view.target_entity_ids) > 3 for view in road_views))

    def test_local_recheck_keeps_one_fixed_view_per_touched_road(self):
        roads = self.city.road_network.segments[:2]
        touched = {item.id for item in roads}
        plan = _local_recheck_plan(self.city, touched, max_views=5)
        selected = plan["selected_views"]
        self.assertTrue(any(view["kind"] == "global" for view in selected))
        for road in roads:
            matching = [
                view for view in selected
                if view["kind"] == "road" and road.id in view["target_entity_ids"]
            ]
            self.assertTrue(matching, road.id)
            self.assertTrue(any(view["view_id"].endswith("_road_a") for view in matching))

    def test_room_archetype_sampling_is_bounded(self):
        plan = AdaptiveObservationPlanner(max_views=20).plan(self.city)
        room_views = [view for view in plan.candidates if view.kind == "room_interior"]
        self.assertGreaterEqual(len(room_views), 1)
        self.assertLessEqual(len(room_views), len(list(self.city.iter_rooms())))

    def test_hero_rooms_are_kept_as_independent_risk_views(self):
        rooms = [room for room in self.city.iter_rooms() if room.function != "corridor"]
        rooms[0].metadata["detail_tier"] = "hero"
        rooms[1].metadata["detail_tier"] = "hero"
        plan = AdaptiveObservationPlanner(max_views=12).plan(
            self.city, risk_entity_ids=[rooms[0].id, rooms[1].id]
        )
        hero_candidates = [
            view for view in plan.candidates
            if view.kind == "room_interior"
            and any(room_id in view.target_entity_ids for room_id in (rooms[0].id, rooms[1].id))
        ]
        self.assertEqual(
            {
                room_id
                for view in hero_candidates
                for room_id in view.target_entity_ids
                if room_id in {rooms[0].id, rooms[1].id}
            },
            {rooms[0].id, rooms[1].id},
        )
        selected_ids = {
            entity_id
            for view in plan.selected_views
            if view.kind == "room_interior"
            for entity_id in view.target_entity_ids
        }
        self.assertTrue({rooms[0].id, rooms[1].id} <= selected_ids)

    def test_furnished_hero_room_gets_adaptive_top_and_corner_views(self):
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.function != "corridor")
        room.metadata["detail_tier"] = "hero"
        center = room.bounds.center
        object_id = f"{room.id}_test_chair"
        floor.objects.append(
            InteriorObject(
                id=object_id,
                room_id=room.id,
                category="chair",
                asset_id="procedural_chair",
                position=Point2D(center.x, center.y),
                width_m=0.6,
                depth_m=0.6,
                height_m=1.0,
            )
        )
        room.object_ids.append(object_id)
        plan = AdaptiveObservationPlanner(max_views=12).plan(
            self.city, risk_entity_ids=[room.id]
        )
        candidates = [
            view for view in plan.candidates
            if view.kind == "room_interior" and room.id in view.target_entity_ids
        ]
        self.assertEqual({view.mode for view in candidates}, {"room"})
        self.assertTrue(any(view.view_id.endswith("_top_00") for view in candidates))
        perspective = next(
            view for view in candidates if view.view_id.endswith("_perspective_00")
        )
        self.assertTrue(
            room.bounds.contains_point(Point2D(*perspective.camera_position[:2]))
        )
        top = next(view for view in candidates if view.view_id.endswith("_top_00"))
        self.assertEqual(top.up, (0.0, 1.0, 0.0))
        self.assertGreater(top.risk_score, perspective.risk_score)

    def test_compiled_room_geometry_reframes_camera_and_filters_partial_room(self):
        building = next(self.city.iter_buildings())
        building.metadata["orientation_deg"] = 0.0
        building.metadata["orientation_contract"] = {"orientation_deg": 0.0}
        floor = building.floors[0]
        rooms = [item for item in floor.rooms if item.function != "corridor"]
        realized, partial = rooms[:2]
        realized.metadata["detail_tier"] = "hero"
        partial.metadata["detail_tier"] = "hero"
        object_id = f"{realized.id}_compiled_chair"
        floor.objects.append(
            InteriorObject(
                id=object_id,
                room_id=realized.id,
                category="chair",
                asset_id="procedural_chair",
                position=Point2D(realized.bounds.center.x, realized.bounds.center.y),
                width_m=0.8,
                depth_m=0.8,
                height_m=1.0,
            )
        )
        realized.object_ids.append(object_id)

        def wall(
            room_id: str,
            suffix: str,
            center: tuple[float, float],
            size: tuple[float, float],
            boundary: float,
        ) -> dict:
            return {
                "id": f"{room_id}_{suffix}",
                "owner_id": room_id,
                "semantic_class": "interior_wall",
                "center": {"x": center[0], "y": center[1], "z": floor.elevation_m + 1.5},
                "size": {"x": size[0], "y": size[1], "z": 3.0},
                "rotation_z_deg": 0.0,
                "metadata": {
                    "room_ids": [room_id],
                    "canonical_boundary": boundary,
                },
            }

        actual = (100.0, 50.0, 110.0, 58.0)
        primitives = [
            wall(realized.id, "south", (105.0, 50.0), (10.0, 0.1), realized.bounds.min_y),
            wall(realized.id, "north", (105.0, 58.0), (10.0, 0.1), realized.bounds.max_y),
            wall(realized.id, "west", (100.0, 54.0), (0.1, 8.0), realized.bounds.min_x),
            wall(realized.id, "east", (110.0, 54.0), (0.1, 8.0), realized.bounds.max_x),
            {
                "id": f"{object_id}_mesh",
                "owner_id": object_id,
                "semantic_class": "furniture_seating",
                "center": {"x": 106.0, "y": 54.0, "z": floor.elevation_m + 0.5},
                "size": {"x": 1.0, "y": 1.0, "z": 1.0},
                "rotation_z_deg": 0.0,
                "metadata": {},
            },
        ]
        # The second room deliberately lacks its east boundary and must never
        # become a render target when compiled geometry is authoritative.
        primitives.extend(
            [
                wall(partial.id, "south", (125.0, 50.0), (10.0, 0.1), partial.bounds.min_y),
                wall(partial.id, "north", (125.0, 58.0), (10.0, 0.1), partial.bounds.max_y),
                wall(partial.id, "west", (120.0, 54.0), (0.1, 8.0), partial.bounds.min_x),
            ]
        )
        plan = AdaptiveObservationPlanner(max_views=20).plan(
            self.city,
            geometry_manifest={"primitives": primitives},
        )
        room_views = [view for view in plan.candidates if view.kind == "room_interior"]
        self.assertTrue(room_views)
        self.assertTrue(all(realized.id in view.target_entity_ids for view in room_views))
        self.assertFalse(any(partial.id in view.target_entity_ids for view in room_views))
        top = next(view for view in room_views if view.view_id.endswith("_top_00"))
        self.assertAlmostEqual(top.look_at[0], (actual[0] + actual[2]) / 2)
        self.assertAlmostEqual(top.look_at[1], (actual[1] + actual[3]) / 2)
        perspective = next(
            view for view in room_views if view.view_id.endswith("_perspective_00")
        )
        self.assertTrue(actual[0] < perspective.camera_position[0] < actual[2])
        self.assertTrue(actual[1] < perspective.camera_position[1] < actual[3])
        self.assertEqual(
            perspective.semantic_context["room_geometry_source"],
            "compiled_manifest",
        )
        self.assertEqual(perspective.semantic_context["realized_wall_count"], 4)

    def test_empty_compiled_geometry_has_no_room_candidates(self):
        plan = AdaptiveObservationPlanner(max_views=12).plan(
            self.city,
            geometry_manifest={"primitives": []},
        )
        self.assertFalse(
            any(view.kind == "room_interior" for view in plan.candidates)
        )

    def test_every_targeted_floor_is_sampled_and_risks_beat_extra_intersections(self):
        city=BaselineCityPlanner().plan(CitySpec(name="hero floor coverage",width_m=180,depth_m=160,
            building_count=3,min_floors=5,max_floors=5,rooms_per_floor=4,seed=19))
        heroes=[]
        for b in city.iter_buildings():
            # Level 1 is neither first, middle nor top.
            for r in [r for r in b.floors[1].rooms if r.function != "corridor"][:3]:
                r.metadata["detail_tier"]="hero";heroes.append(r.id)
        plan=AdaptiveObservationPlanner(max_views=18).plan(city,risk_entity_ids=heroes)
        self.assertFalse(plan.uncovered_risk_entity_ids)
        self.assertTrue(set(heroes)<=set(plan.covered_entity_ids))

    def test_explicit_realized_isolation_caps_count_but_door_headers_do_not(self):
        from cityg.observation import _RealizedRoomIndex,_RealizedPrimitive
        room=next(r for r in self.city.iter_rooms() if r.function != "corridor")
        def cap(side,role="room_view_cap"):
            return _RealizedPrimitive(room.id,"interior_wall",(0,0,1),(1,.1,3),0,
                {"wall_role":role,"wall_side":side,"room_isolation_cap":True})
        walls=[cap(s) for s in ("north","south","west","east")]
        self.assertTrue(_RealizedRoomIndex._has_all_canonical_boundaries(room,walls))
        self.assertFalse(_RealizedRoomIndex._has_all_canonical_boundaries(room,[*walls[:3],cap("east","door_header")]))


if __name__ == "__main__":
    unittest.main()
