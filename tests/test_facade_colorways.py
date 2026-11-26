import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cityg.assets import MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.facade_colorways import apply_facade_colorways, select_warm_buildings, VERSION
from cityg.geometry.model import GeometryScene, MaterialSpec, Vec3
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.services import OpenUSDBackend


class FacadeColorwayTests(unittest.TestCase):
    def setUp(self):
        self.city = BaselineCityPlanner().plan(CitySpec(building_count=3,min_floors=2,max_floors=2))
        self.buildings = list(self.city.iter_buildings())
        self.compiler = GeometryCompiler(include_interiors=False)
        material = MaterialSpec('residential_brick',(.82,.68,.56),base_color_path='/example/albedo.jpg',
                                normal_path='/example/normal.jpg',texture_scale_m=2)
        self.scene = GeometryScene(self.city.id,self.city.coordinate_system,materials=[material])
        for b in self.buildings:
            self.scene.primitives.append(self.compiler._box(b.id+'_wall',b.id,Vec3(1,2,3),Vec3(4,5,6),0,
                'exterior_wall',material.id,'shell'))

    def test_scoped_idempotent_reversible_and_preserves_maps(self):
        original = to_primitive(self.scene.primitives)
        b = self.buildings[0]; b.metadata['facade_colorway']='cool_gray'
        report = apply_facade_colorways(self.city,self.scene)
        self.assertEqual(report['building_count'],1)
        self.assertEqual(to_primitive(self.scene.primitives[1:]),original[1:])
        changed = self.scene.primitives[0]
        self.assertEqual(changed.center,Vec3(1,2,3))
        self.assertEqual(changed.metadata[VERSION]['original_material_id'],'residential_brick')
        variant = next(m for m in self.scene.materials if m.id==changed.material_id)
        self.assertEqual(variant.base_color_path,'/example/albedo.jpg')
        self.assertEqual(variant.normal_path,'/example/normal.jpg')
        self.assertLess(variant.display_color[0],variant.display_color[2])
        snapshot = to_primitive(self.scene)
        apply_facade_colorways(self.city,self.scene)
        self.assertEqual(to_primitive(self.scene),snapshot)
        b.metadata.pop('facade_colorway')
        apply_facade_colorways(self.city,self.scene)
        self.assertEqual(to_primitive(self.scene.primitives),original)

    def test_floor_scope_glass_and_embedded_assets(self):
        b=self.buildings[0]; b.metadata['facade_colorway']='pearl_gray'
        self.scene.primitives[0].owner_id=b.floors[0].id
        p=self.scene.primitives[0]
        self.scene.primitives += [replace(p,id='glass',semantic_class='facade_window'),
                                 replace(p,id='glb',metadata={'resolved_asset':True})]
        apply_facade_colorways(self.city,self.scene)
        self.assertIn('__colorway_',p.material_id)
        self.assertEqual(self.scene.primitives[-1].material_id,'residential_brick')
        self.assertEqual(self.scene.primitives[-2].material_id,'residential_brick')

    def test_selection_and_invalid_palette(self):
        selected=select_warm_buildings(self.city,self.scene,2)
        self.assertEqual(len(set(selected)),2)
        self.assertEqual(selected,select_warm_buildings(self.city,self.scene,2))
        self.assertEqual(select_warm_buildings(self.city,self.scene,0),[])
        self.buildings[0].metadata['facade_colorway']='invalid'
        with self.assertRaises(ValueError):apply_facade_colorways(self.city,self.scene)

    def test_scene_only_materials_export_portably(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); texture=root/'map.jpg'; texture.write_bytes(b'test texture')
            self.scene.materials=[replace(self.scene.materials[0],base_color_path=str(texture),normal_path=None)]
            self.buildings[0].metadata['facade_colorway']='muted_sage'
            apply_facade_colorways(self.city,self.scene)
            self.compiler.material_library=MaterialLibrary()
            out=root/'export'
            OpenUSDBackend(self.compiler)._export_material_library(self.scene,out)
            for material in self.scene.materials:
                self.assertFalse(Path(material.base_color_path).is_absolute())
                self.assertEqual((out/material.base_color_path).read_bytes(),b'test texture')

    def test_full_compile_applies_stored_request(self):
        b=self.buildings[0]; b.metadata['facade_colorway']='cool_gray'
        scene=self.compiler.compile(self.city)
        changed=[p for p in scene.primitives if VERSION in p.metadata]
        self.assertTrue(changed)
        self.assertTrue(all(p.metadata[VERSION]['building_id']==b.id for p in changed))


if __name__=='__main__':unittest.main()
