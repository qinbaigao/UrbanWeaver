from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cityg.schemas import Building,Floor,Room,Door,Bounds2D,Point2D,VerticalConnector
from cityg.planning.interior_frame import InteriorFrame
from cityg.planning.joint_inventory_capacity import end_bay_proposals,floor_capacity,repair_joint_capacity


def fixture(axis='x', entry='east'):
    rooms=[Room('hall','Hall','corridor',Bounds2D(0,3,24,5)),
           Room('office','Office','open_office',Bounds2D(0,0,12,3)),
           Room('meet1','Meeting','meeting_room',Bounds2D(12,0,18,3)),
           Room('meet2','Meeting','meeting_room',Bounds2D(18,0,24,3)),
           Room('store','Storage','storage',Bounds2D(0,5,12,8)),
           Room('wait','Waiting','reception',Bounds2D(12,5,24,8))]
    ep=Point2D(24 if entry=='east' else 0,4)
    doors=[Door('exterior','hall',None,ep,1.6,'exterior')]
    for r in rooms[1:]:
        doors.append(Door(r.id+'_door',r.id,'hall',Point2D(r.bounds.center.x,3 if r.bounds.max_y==3 else 5)))
    f=Floor('floor',0,0,3.2,rooms,doors)
    b=Building('b','Building','commercial',Bounds2D(0,0,24,8),ep,floors=[f],
               vertical_connectors=[VerticalConnector('stairs','stairs',Bounds2D(11,3.2,13,4.8),0,2)])
    b.metadata['interior_layout_contract']={'circulation_axis':axis,'requirements':[{
        'levels':[0],'required_functions':['meeting_room','open_office','reception','storage'],
        'inventory':[{'room_function':'meeting_room','category':'meeting_table','min_count':1},
                     {'room_function':'meeting_room','category':'meeting_chair','min_count':6}]}]}
    if axis=='y':
        frame=InteriorFrame('y');b.footprint=frame.bounds(b.footprint);b.entrance=frame.point(b.entrance)
        b.vertical_connectors=[replace(c,bounds=frame.bounds(c.bounds)) for c in b.vertical_connectors]
        f=frame.floor(f);b.floors=[f]
    return b,f


class JointInventoryCapacityTests(unittest.TestCase):
    def test_bay_preserves_area_entry_core_and_functions_for_four_entry_sides(self):
        for axis in ('x','y'):
            for entry in ('west','east'):
                b,f=fixture(axis,entry);old=deepcopy(f)
                offers=end_bay_proposals(b,f,'meeting_room')
                self.assertTrue(offers,(axis,entry))
                self.assertLessEqual(len(offers),4)
                for _,new in offers:
                    self.assertAlmostEqual(sum(r.bounds.area for r in new.rooms),b.footprint.area)
                    self.assertEqual({r.function for r in new.rooms},{r.function for r in f.rooms})
                    self.assertEqual(new.doors[0],f.doors[0])
                    hall=next(r for r in new.rooms if r.function=='corridor')
                    self.assertTrue(hall.bounds.contains_bounds(b.vertical_connectors[0].bounds))
                    self.assertEqual(sum(r.function=='meeting_room'for r in new.rooms),1)
                self.assertEqual(f,old)

    def test_furniture_private_units_locks_and_semantic_layout_are_not_repartitioned(self):
        for kind in ('furniture','private','locked','semantic'):
            b,f=fixture()
            if kind=='furniture':f.rooms[1].object_ids=['accepted']
            if kind=='private':f.metadata['dwelling_units']=[{'id':'home'}]
            if kind=='locked':f.rooms[1].metadata['protected']=True
            if kind=='semantic':f.metadata['spatial_layout']={'status':'accepted'}
            self.assertEqual(end_bay_proposals(b,f,'meeting_room'),[],kind)

    def test_cannot_cut_a_core_or_relocate_exterior_door(self):
        b,f=fixture();b.vertical_connectors[0].bounds=Bounds2D(1,3.2,3,4.8)
        self.assertEqual(end_bay_proposals(b,f,'meeting_room'),[])
        b,f=fixture();f.doors[0].position=Point2D(12,8)
        self.assertEqual(end_bay_proposals(b,f,'meeting_room'),[])

    def test_seats_are_assigned_to_one_complete_bundle_not_split_three_plus_three(self):
        b,f=fixture();calls=[]
        def witness(b,f,r,items,resolver,**kwargs):
            calls.append(items);return None,{'status':'metric_witness','tested':1}
        with patch('cityg.planning.joint_inventory_capacity.find_inventory_witness',side_effect=witness):
            result=floor_capacity(b,f,None)
        self.assertEqual(result['status'],'references_fit');self.assertEqual(len(calls),1)
        self.assertEqual({i['category']:i['min_count']for i in calls[0]}, {'meeting_table':1,'meeting_chair':6})

    def test_missing_required_function_is_not_certified(self):
        b,f=fixture();f.rooms=[r for r in f.rooms if r.function!='reception']
        with patch('cityg.planning.joint_inventory_capacity.find_inventory_witness',return_value=(None,{'status':'metric_witness','tested':1})):
            self.assertIn('reception',floor_capacity(b,f,None)['failed_functions'])

    def test_failed_compilation_rolls_back_and_fixed_partition_skips(self):
        b,f=fixture();city=SimpleNamespace(buildings=[b],world_program=None)
        # A method referring to self remains bound to the detached copy.
        class CityFixture(SimpleNamespace):
            def iter_buildings(self):return iter(self.buildings)
        city=CityFixture(buildings=[b],world_program=None);old=deepcopy(city)
        def capacity(b,f,*args,**kwargs):
            return {'status':'references_fit' if f.metadata.get('joint_capacity_replan') else 'unresolved',
                    'failed_functions':['meeting_room'],'checks':[{}]}
        compiler=SimpleNamespace(compile=lambda *a,**k:(_ for _ in ()).throw(ValueError('compile rejected')))
        with patch('cityg.planning.joint_inventory_capacity.floor_capacity',side_effect=capacity):
            result,report=repair_joint_capacity(city,compiler,None,{'b':[0]})
            self.assertEqual(report['floors'][0]['status'],'rejected');self.assertEqual(result,old)
            result,report=repair_joint_capacity(city,compiler,None,{'b':[0]},preserve_partition=True)
            self.assertFalse(report['floors'][0]['attempts']);self.assertEqual(city,old)

    def test_unselected_levels_do_not_change(self):
        b,f=fixture()
        class CityFixture(SimpleNamespace):
            def iter_buildings(self):return iter(self.buildings)
        city=CityFixture(buildings=[b]);old=deepcopy(city)
        result,report=repair_joint_capacity(city,None,None,{})
        self.assertEqual(result,old);self.assertFalse(report['floors'])
