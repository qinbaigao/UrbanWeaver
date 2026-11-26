import unittest
from dataclasses import replace
from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene, MaterialSpec, Vec3
from cityg.geometry.roof_textures import apply_roof_textures, texture_choice, VERSION
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive


class RoofTextureTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner().plan(CitySpec(building_count=1,min_floors=2,max_floors=2))
        self.b=next(self.city.iter_buildings())
        self.b.metadata['roof_texture']='gravel_gray'
        self.compiler=GeometryCompiler(include_interiors=False)
        roof=self.compiler._box('roof',self.b.id,Vec3(2,3,8),Vec3(25,20,.2),23,'roof','roof','shell')
        self.scene=GeometryScene(self.city.id,self.city.coordinate_system,
            materials=[MaterialSpec('roof',(.5,.5,.5)),MaterialSpec('gravel_warm',(.6,.5,.4),base_color_path='gravel.jpg')],
            primitives=[roof,replace(roof,id='course',semantic_class='roof_surface_detail',
                material_id='roofscape_tone_roof_1',metadata={'roof_system':'roofscape_v1'}),
                replace(roof,id='wall',semantic_class='exterior_wall'),
                replace(roof,id='equipment',semantic_class='roof_equipment'),
                replace(roof,id='pitched',metadata={'roof_style':'pitched'}),
                replace(roof,id='glb',metadata={'resolved_asset':True})])

    def test_geometry_preserved_overlays_rebound_and_other_assets_untouched(self):
        old=to_primitive(self.scene.primitives)
        report=apply_roof_textures(self.city,self.scene)
        self.assertEqual(report['rebound_primitives'],2)
        self.assertEqual(to_primitive(self.scene.primitives[2:]),old[2:])
        for p,original in zip(self.scene.primitives,old):
            current=to_primitive(p);current.pop('material_id');original.pop('material_id')
            current['metadata'].pop(VERSION,None)
            self.assertEqual(current,original)
        self.assertTrue(all(p.material_id.startswith(VERSION) for p in self.scene.primitives[:2]))

    def test_idempotence_and_reversible(self):
        old=to_primitive(self.scene.primitives)
        apply_roof_textures(self.city,self.scene);once=to_primitive(self.scene)
        apply_roof_textures(self.city,self.scene);self.assertEqual(once,to_primitive(self.scene))
        self.b.metadata.pop('roof_texture');apply_roof_textures(self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene.primitives))

    def test_missing_map_retains_original_and_invalid_choice_is_atomic(self):
        self.scene.materials=[self.scene.materials[0]];old=to_primitive(self.scene.primitives)
        report=apply_roof_textures(self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene.primitives));self.assertTrue(report['missing_texture_primitives'])
        self.b.metadata['roof_texture']='lava';old=to_primitive(self.scene)
        with self.assertRaises(ValueError):apply_roof_textures(self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene))

    def test_metal_and_explicit_choice(self):
        self.b.metadata.pop('roof_texture');self.b.metadata['roof_finish']='silver_metal'
        self.assertEqual(texture_choice(self.b),'original')
        self.b.metadata['roof_texture']='pavers';self.assertEqual(texture_choice(self.b),'pavers')


if __name__=='__main__':unittest.main()
