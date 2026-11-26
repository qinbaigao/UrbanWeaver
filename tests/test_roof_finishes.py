import unittest
from dataclasses import replace

from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.roof_finishes import apply_roof_finishes, assign_roof_finishes, VERSION
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive


class RoofFinishTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner().plan(CitySpec(building_count=3,min_floors=2,max_floors=2))
        self.buildings=list(self.city.iter_buildings()); self.compiler=GeometryCompiler(include_interiors=False)
        self.scene=GeometryScene(self.city.id,self.city.coordinate_system,materials=self.compiler._materials())
        for b in self.buildings:
            self.scene.primitives.append(self.compiler._box(b.id+'_roof',b.id,Vec3(1,2,7),Vec3(4,5,.2),0,
                'roof','roof','shell'))

    def test_scoped_reversible_idempotent(self):
        original=to_primitive(self.scene.primitives)
        self.buildings[0].metadata['roof_finish']='graphite'
        r=apply_roof_finishes(self.city,self.scene)
        self.assertEqual(r['roof_count'],1)
        self.assertEqual(self.scene.primitives[0].material_id,'roof_finish_graphite')
        self.assertEqual(to_primitive(self.scene.primitives[1:]),original[1:])
        before=to_primitive(self.scene)
        apply_roof_finishes(self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene))
        self.buildings[0].metadata.pop('roof_finish')
        apply_roof_finishes(self.city,self.scene)
        self.assertEqual(original,to_primitive(self.scene.primitives))

    def test_protect_pitched_assets_and_nonroof_surfaces(self):
        self.buildings[0].metadata['roof_finish']='cool_membrane'
        p=self.scene.primitives[0]
        self.scene.primitives += [replace(p,id='pitched',metadata={'roof_style':'pitched'}),
            replace(p,id='glb',metadata={'resolved_asset':True}),
            replace(p,id='wall',semantic_class='exterior_wall')]
        apply_roof_finishes(self.city,self.scene)
        self.assertTrue(all(p.material_id=='roof' for p in self.scene.primitives[-3:]))

    def test_floor_owned_roof_and_equipment(self):
        b=self.buildings[0]; b.metadata['roof_finish']='concrete_gray'
        p=self.scene.primitives[0];p.owner_id=b.floors[-1].id
        self.scene.primitives.append(replace(p,id='hvac',semantic_class='roof_auxiliary'))
        r=apply_roof_finishes(self.city,self.scene)
        self.assertEqual(r['equipment_corrected'],1)
        self.assertEqual(p.material_id,'roof_finish_concrete_gray')
        self.assertEqual(self.scene.primitives[-1].material_id,'roof_finish_silver_metal')
        self.assertEqual(self.scene.primitives[-1].metadata[VERSION]['finish'],'silver_metal')

    def test_stable_choices_preserve_explicit_and_validate(self):
        b=self.buildings[0];b.metadata['roof_finish']='silver_metal'
        assign_roof_finishes(self.city)
        self.assertEqual(b.metadata['roof_finish'],'silver_metal')
        before=[b.metadata['roof_finish'] for b in self.buildings]
        assign_roof_finishes(self.city)
        self.assertEqual(before,[b.metadata['roof_finish'] for b in self.buildings])
        b.metadata['roof_finish']='invalid'
        with self.assertRaises(ValueError):apply_roof_finishes(self.city,self.scene)

    def test_compile_retains_facade_colour_and_roof_choice(self):
        b=self.buildings[0];b.metadata.update(roof_finish='cool_membrane',facade_colorway='cool_gray')
        scene=self.compiler.compile(self.city)
        self.assertTrue(any(VERSION in p.metadata for p in scene.primitives))
        self.assertTrue(any('facade_colorway_v1' in p.metadata for p in scene.primitives))
        source=next(m for m in scene.materials if m.id=='roof_finish_cool_membrane')
        self.assertIsNone(source.base_color_path)


if __name__=='__main__':unittest.main()
