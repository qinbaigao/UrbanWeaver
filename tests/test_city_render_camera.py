import copy
import math
from pathlib import Path
import unittest
from scripts.city_render.camera import aerial_camera
from scripts.city_render.gltf_compat import static_tree


def fixture():
    f=1/math.tan(math.radians(46)/2);a=1110/921;n=12;z=22000
    return {'schema':'cityg.render_view','schema_version':1,
        'coordinate_system':{'space':'scene_world','up_axis':'Z','units':'meters','handedness':'right','matrix_layout':'column_major','quaternion_order':'xyzw'},
        'scene_ref':{'original_source':'/scene','total_primitives':435491},
        'selection':{'district_id':'all'},'visibility':{'mode':'overview','auto_cutaway':True,'show_grid':True},
        'lighting':{'render_profile':'navigation'},'replay':{'loaded':False},
        'camera':{'projection':'perspective','camera_position':[-274,900,357],'look_at':[201,732,46],
            'quaternion_xyzw':[0,0,0,1],'matrix_world':[1,0,0,0,0,1,0,0,0,0,1,0,-274,900,357,1],
            'projection_matrix':[f/a,0,0,0,0,f,0,0,0,0,-(z+n)/(z-n),-1,0,0,-2*z*n/(z-n),0],
            'vertical_fov_deg':46,'aspect':a,'near_clip_m':n,'far_clip_m':z}}


class CityRenderCameraTests(unittest.TestCase):
    def test_navigation_handoff_preserves_exact_composition(self):
        doc=fixture();before=copy.deepcopy(doc)
        result=aerial_camera(doc,Path('/scene'),435491,3330)
        self.assertEqual(result['height'],2763)
        self.assertEqual(result['position'],[-274,900,357])
        self.assertAlmostEqual(result['pixel_aspect_x'],1)
        self.assertEqual(result['near'],12)
        self.assertEqual(doc,before)

    def test_rejects_wrong_package_and_nonintact_scope(self):
        for section,key,value in [('scene_ref','original_source','/other'),('scene_ref','total_primitives',1),
             ('visibility','mode','room'),('visibility','xray_shells',True),('selection','district_id','d1'),
             ('camera','film_offset_mm',2),('camera','vertical_fov_deg',60)]:
            doc=fixture();doc[section][key]=value
            with self.assertRaises(ValueError):aerial_camera(doc,Path('/scene'),435491,3330)

    def test_keeps_frustum_with_noninteger_pixel_aspect(self):
        result=aerial_camera(fixture(),Path('/scene'),435491,1200)
        self.assertAlmostEqual(1200/result['height']*result['pixel_aspect_x'],1110/921)


class StaticGraphTests(unittest.TestCase):
    def test_expands_shared_nodes_without_changing_meshes_materials_or_transforms(self):
        doc={'scenes':[{'nodes':[0,1]}],'nodes':[{'translation':[1,0,0],'children':[2]},
             {'translation':[0,1,0],'children':[2]},{'mesh':0,'scale':[2,3,4]}],
             'meshes':[{'primitives':[{'attributes':{'POSITION':0},'material':0}]}],
             'materials':[{'name':'original'}]}
        before=copy.deepcopy(doc);tree,changed=static_tree(doc)
        self.assertTrue(changed);self.assertEqual(doc,before)
        self.assertEqual(tree['meshes'],doc['meshes']);self.assertEqual(tree['materials'],doc['materials'])
        parents=[tree['nodes'][i] for i in tree['scenes'][0]['nodes']]
        self.assertNotEqual(parents[0]['children'],parents[1]['children'])
        for parent in parents:self.assertEqual(tree['nodes'][parent['children'][0]],doc['nodes'][2])
        self.assertEqual([p['translation'] for p in parents],[[1,0,0],[0,1,0]])

    def test_valid_tree_is_not_rewritten(self):
        doc={'scenes':[{'nodes':[0]}],'nodes':[{'children':[1]},{'mesh':0}]}
        tree,changed=static_tree(doc)
        self.assertFalse(changed);self.assertIs(tree,doc)

    def test_unreachable_modelling_helpers_do_not_enter_rendered_scene(self):
        doc={'scenes':[{'nodes':[0]}],'nodes':[{'children':[1]},{'mesh':0},{'mesh':1,'scale':[100,100,100]}],
             'meshes':[{'name':'visible entrance'},{'name':'unused source modelling ground'}]}
        tree,changed=static_tree(doc)
        self.assertTrue(changed);self.assertEqual(len(tree['nodes']),2)
        self.assertEqual(tree['meshes'],doc['meshes'])
