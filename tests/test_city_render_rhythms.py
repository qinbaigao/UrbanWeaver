import math
import unittest
from scripts.city_render.facade_rhythms import panels, plan, coordinates, split_rows, split_columns


def window(bay=0, floor=1, x=None, rotation=0):
    u=bay*3 if x is None else x; angle=math.radians(rotation)
    return {'id':f'b_window_{floor}_{bay}', 'owner_id':f'b_floor_{floor}', 'layer_id':'shell:b',
            'primitive_type':'box', 'semantic_class':'facade_window','material_id':'glass',
            'center':{'x':u*math.cos(angle)-10*math.sin(angle),'y':u*math.sin(angle)+10*math.cos(angle),'z':floor*3+1.5},
            'size':{'x':2.2,'y':.035,'z':2},'rotation_z_deg':rotation,'collision_enabled':False,
            'metadata':{'massing_part':0,'facade_side':'north','floor_level':floor,'facade_style':'residential_brick_v1'}}


class FacadeRhythmTests(unittest.TestCase):
    def test_ribbon_fits_existing_horizontal_span_and_rotates(self):
        for angle in (0,27,90):
            rows=[window(i,rotation=angle) for i in range(4)]
            result=panels(rows,'horizontal_ribbon');glass=result[0]
            u,_,width=coordinates(glass)
            self.assertAlmostEqual(u-width/2,-1.1);self.assertAlmostEqual(u+width/2,10.1)
            self.assertAlmostEqual(glass['size']['z'],1.76)
            self.assertEqual(sum(p['semantic_class']=='facade_window' for p in result),1)

    def test_no_bridge_over_courtyard_or_missing_floor(self):
        self.assertEqual(len(split_rows([window(0),window(1),window(8)])),2)
        rows=[window(floor=i) for i in (1,2,4)]
        self.assertEqual([len(r) for r in split_columns(rows)],[2,1])

    def test_vertical_and_double_storey_grouping(self):
        rows=[window(floor=i) for i in range(1,5)]
        vertical=[p for p in panels(rows,'vertical_strip') if p['semantic_class']=='facade_window']
        paired=[p for p in panels(rows,'paired_storeys') if p['semantic_class']=='facade_window']
        self.assertEqual(len(vertical),1);self.assertEqual(vertical[0]['size']['z'],11)
        self.assertEqual(len(paired),2);self.assertTrue(all(p['size']['z']==5 for p in paired))

    def test_ground_floor_and_unselected_building_preserved(self):
        rows=[window(bay=b,floor=f) for f in range(4) for b in range(3)]
        other={**window(), 'id':'c_window', 'layer_id':'shell:c'}
        removed,added,report=plan(rows+[other],{'b':'horizontal_ribbon'})
        self.assertEqual(report['building_count'],1)
        self.assertNotIn('c_window',removed)
        self.assertTrue(all(p['id'] not in removed for p in rows if p['metadata']['floor_level']==0))
        self.assertEqual(len(removed),9)
        self.assertEqual(len(added),len({p['id'] for p in added}))

    def test_curtainwall_skipped(self):
        rows=[window(floor=f) for f in range(4)]
        rows[0]['metadata']['facade_style']='commercial_curtainwall_v1'
        removed,added,report=plan(rows,{'b':'horizontal_ribbon'})
        self.assertFalse(removed);self.assertFalse(added)
        self.assertEqual(report['skipped_buildings'],['b'])

    def test_balcony_face_preserved_without_blocking_other_faces(self):
        rows=[window(bay=b,floor=f) for f in range(4) for b in range(3)]
        south=[]
        from copy import deepcopy
        for p in rows:
            q=deepcopy(p);q['metadata']['facade_side']='south';q['center']['y']=-10;q['id']+='south'
            south.append(q)
        balcony={**south[-1], 'id':'balcony', 'semantic_class':'balcony_slab'}
        removed,added,report=plan(rows+south+[balcony],{'b':'horizontal_ribbon'})
        self.assertEqual(report['building_count'],1)
        self.assertTrue(all(p['id'] not in removed for p in south+[balcony]))
        self.assertTrue(added)
