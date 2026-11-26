import copy
import json
import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from cityg.envelopes import SHAPES, envelope_contract, validate_envelope
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.incremental import merge_building_scene
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive, city_from_dict
from cityg.services import OpenUSDBackend
from cityg.refinement.building import BuildingRefinementPlan, apply_building_refinement


class EnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = BaselineCityPlanner().plan(CitySpec(name="envelope", width_m=200, depth_m=180,
            building_count=2, min_floors=3, max_floors=3, rooms_per_floor=2,
            buildings_per_block=1, architecture={"envelope": {"shape": "ellipse", "facade_system": "curtain_wall"}}))

    def test_all_shapes_profiles_fit_rotated_envelope(self):
        building = copy.deepcopy(next(self.city.iter_buildings()))
        for shape in SHAPES:
            for profile in ("straight","taper","lean"):
                building.metadata["appearance_plan"]["envelope"] = {"shape":shape,"profile":profile}
                building.metadata["orientation_deg"] = 37
                contract = envelope_contract(building)
                self.assertEqual(len(contract["rings"]), len(building.floors)+1)
                for ring in contract["rings"]:
                    for x,y,z in ring:
                        self.assertTrue(building.footprint.min_x <= x <= building.footprint.max_x)
                        self.assertTrue(building.footprint.min_y <= y <= building.footprint.max_y)
                    self.assertEqual(len({p[2] for p in ring}), 1)
                self.assertFalse(contract["interior_supported"])

    def test_explicit_empty_interior_scope_keeps_envelopes_exterior_only(self):
        city=copy.deepcopy(self.city)
        city.metadata['interior_scope']={'building_levels':{},'policy':'test_exterior_only'}
        scene=GeometryCompiler(include_interiors=True).compile(city)
        self.assertTrue(scene.metadata['exterior_only_building_ids'])
        self.assertFalse(any(p.semantic_class=='interior_wall' for p in scene.primitives))
        building=next(city.iter_buildings())
        city.metadata['interior_scope']['building_levels'][building.id]=[0]
        with self.assertRaisesRegex(ValueError,'include_interiors=False'):
            GeometryCompiler(include_interiors=True).compile(city)

    def test_reject_invalid_parameters(self):
        for config in ({"shape":"freeform"}, {"profile":"twist"}, {"top_scale":.8},
                       {"profile":"lean","lean_x":.4}, {"segments":True},
                       {"profile":"taper","top_scale":float('nan')}, {"unknown":1}):
            with self.assertRaises(ValueError):
                validate_envelope(config)

    def test_actual_mesh_closed_and_outdoor_navigation_only(self):
        scene = GeometryCompiler(include_interiors=False).compile(self.city)
        result = GeometryValidator().validate(self.city,scene)
        self.assertTrue(result.ok,result.to_dict())
        self.assertIsNone(result.metrics["outdoor_to_room_path_ratio"])
        self.assertFalse(any(n.node_type in {"room","corridor"} for n in scene.navigation.nodes))
        self.assertEqual(sum(n.node_type == "exterior_door" for n in scene.navigation.nodes), 2)
        self.assertGreater(result.metrics["curtain_wall_panel_count"],0)
        for p in scene.primitives:
            if not p.metadata.get("exterior_envelope") or p.primitive_type != "path_mesh":
                continue
            counts=Counter(tuple(sorted((f[i],f[(i+1)%3]))) for f in p.metadata['mesh_triangles'] for i in range(3))
            self.assertTrue(all(v==2 for v in counts.values()),p.id)
        self.assertFalse(scene.state_machines)

    def test_all_shapes_compile_punched_and_glass(self):
        city=copy.deepcopy(self.city)
        for shape in SHAPES:
            for facade in ("punched","curtain_wall"):
                for b in city.iter_buildings():
                    b.metadata['appearance_plan']['envelope']={'shape':shape,'profile':'taper','facade_system':facade}
                scene=GeometryCompiler(include_interiors=False).compile(city)
                report=GeometryValidator().validate(city,scene)
                self.assertTrue(report.ok,report.to_dict())

    def test_interior_compile_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError,"include_interiors=False"):
            GeometryCompiler().compile(self.city)

    def test_taper_normals_are_tilted_and_roundtrip(self):
        city=copy.deepcopy(self.city)
        for b in city.iter_buildings():
            b.metadata['appearance_plan']['envelope'].update(profile='taper',top_scale=.65)
        restored=city_from_dict(json.loads(json.dumps(to_primitive(city))))
        self.assertEqual(envelope_contract(next(city.iter_buildings())),envelope_contract(next(restored.iter_buildings())))
        scene=GeometryCompiler(include_interiors=False).compile(restored)
        glass=[p for p in scene.primitives if p.semantic_class=='curtain_wall_glass']
        self.assertTrue(all(abs(panel['surface_normal'][2])>.001 for p in glass for panel in p.metadata['panels']))

    def test_validation_detects_broken_collision_and_missing_route(self):
        scene=GeometryCompiler(include_interiors=False).compile(self.city)
        hull=next(p for p in scene.primitives if p.semantic_class=='collision_envelope')
        hull.metadata['mesh_triangles'].pop()
        scene.navigation.nodes=[n for n in scene.navigation.nodes if n.node_type!='exterior_door']
        codes={i.code for i in GeometryValidator().validate(self.city,scene).issues}
        self.assertIn('exterior_collision_open',codes)
        self.assertIn('exterior_entrance_coverage',codes)

    def test_incremental_matches_full_and_preserves_other_contracts(self):
        city=copy.deepcopy(self.city)
        compiler=GeometryCompiler(include_interiors=False)
        previous=compiler.compile(city)
        b=next(city.iter_buildings())
        result=apply_building_refinement(city,BuildingRefinementPlan(b.id,'adjust silhouette',
            {'envelope_adjustment':{'shape':'trapezoid','profile':'lean','lean_x':.12,'facade_system':'curtain_wall'}}))
        city=result.city
        subset=compiler.compile(city,building_ids={b.id})
        merged,_=merge_building_scene(city,previous,subset,{b.id})
        full=compiler.compile(city)
        self.assertEqual(merged.metadata['exterior_envelopes'],full.metadata['exterior_envelopes'])
        self.assertEqual(to_primitive(merged.navigation),to_primitive(full.navigation))
        self.assertEqual({p.id:to_primitive(p) for p in merged.primitives},{p.id:to_primitive(p) for p in full.primitives})
        self.assertTrue(GeometryValidator().validate(city,merged).ok)

    def test_validation_handles_malformed_collision(self):
        scene=GeometryCompiler(include_interiors=False).compile(self.city)
        hull=next(p for p in scene.primitives if p.semantic_class=='collision_envelope')
        hull.metadata['mesh_triangles'][0]=[0,1]
        codes={i.code for i in GeometryValidator().validate(self.city,scene).issues}
        self.assertIn('exterior_collision_invalid',codes)

    def test_usd_exports_glass_and_invisible_real_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            OpenUSDBackend(GeometryCompiler(include_interiors=False)).compile(copy.deepcopy(self.city),root)
            text='\n'.join(p.read_text() for p in (root/'usd/layers/buildings').glob('*_shell.usda'))
            self.assertIn('UsdPreviewSurface',text)
            self.assertIn('rel material:binding',text)
            self.assertIn('PhysicsMeshCollisionAPI',text)
            self.assertIn('token visibility = "invisible"',text)


if __name__=='__main__':
    unittest.main()
