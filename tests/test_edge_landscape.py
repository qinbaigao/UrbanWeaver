from collections import Counter
from copy import deepcopy
import unittest
from unittest.mock import patch

from cityg.geometry import GeometryCompiler
from cityg.geometry.edge_landscape import (Heightfield, KEY, VERSION, compile_edge_landscape,
                                          plan_extension, terrain_meshes)
from cityg.geometry.model import GeometryScene
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive


class EdgeLandscapeTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner().plan(CitySpec(width_m=400,depth_m=500,building_count=3,
                                                    min_floors=1,max_floors=1))
        self.compiler=GeometryCompiler(include_interiors=False)

    def test_extension_preserves_city_and_refuses_double_extension(self):
        before=to_primitive([self.city.districts,self.city.road_network,self.city.rivers])
        old=self.city.bounds
        plan=plan_extension(self.city)
        self.assertEqual(self.city.bounds.min_x,old.min_x-260)
        self.assertEqual(self.city.bounds.max_x,old.max_x+340)
        self.assertEqual(before,to_primitive([self.city.districts,self.city.road_network,self.city.rivers]))
        self.assertEqual(len(plan['entrances']['west']),3)
        with self.assertRaises(ValueError):plan_extension(self.city)

    def test_heightfield_contact_edges_peak_and_watertight_ground(self):
        f=Heightfield(dict(min_x=0,min_y=0,max_x=340,max_y=1000),54,6)
        self.assertAlmostEqual(f(0,500),0)
        self.assertAlmostEqual(f(340,500),0,places=5)
        self.assertGreater(max(p[2] for p in f.points),40)
        for x,y,z in f.points[::87]:self.assertAlmostEqual(f(x,y),z,places=5)
        mesh=terrain_meshes(self.city,f,'test')[0]
        faces=mesh.metadata['mesh_triangles']
        edges=Counter(tuple(sorted((a,b))) for t in faces for a,b in zip(t,t[1:]+t[:1]))
        self.assertEqual(set(edges.values()),{2})
        self.assertTrue(mesh.collision_enabled)

    def test_additive_idempotent_paths_and_existing_scene(self):
        plan=plan_extension(self.city)
        plan.update(park_tree_count=0,hill_tree_count=0,grid_step_m=15)
        scene=GeometryScene(self.city.id,self.city.coordinate_system,materials=self.compiler._materials())
        with patch.object(self.compiler,'_outdoor_mesh',return_value=None):
            report=compile_edge_landscape(self.compiler,self.city,scene)
            before=to_primitive(scene)
            compile_edge_landscape(self.compiler,self.city,scene)
        self.assertEqual(before,to_primitive(scene))
        self.assertEqual(len(report['sites']),2)
        self.assertFalse(report['navigation_graph_extended'])
        paths=[p for p in scene.primitives if p.semantic_class=='landscape_path']
        self.assertGreaterEqual(len(paths),10)
        self.assertTrue(all(p.metadata['terrain_draped'] for p in paths))
        self.assertTrue(any(p.center.z>5 for p in paths))

    def test_absent_plan_no_change_and_bad_version_fails(self):
        scene=GeometryScene(self.city.id,self.city.coordinate_system)
        before=to_primitive(scene)
        self.assertIsNone(compile_edge_landscape(self.compiler,self.city,scene))
        self.assertEqual(before,to_primitive(scene))
        self.city.metadata[KEY]={'version':'bad'}
        with self.assertRaises(ValueError):compile_edge_landscape(self.compiler,self.city,scene)


if __name__=='__main__':unittest.main()
