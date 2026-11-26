from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from cityg.schemas import Room, Bounds2D, InteriorObject, Point2D
from cityg.planning.functional_configuration import options, validate_plan, target_inventory, evaluate_configuration


def plan(function='open_office', recipe='workstation', n=3, seats=1):
    return validate_plan({'reason': 'Shared workspace with purposeful service capacity',
        'intentional_open_space': 'Keep entrance and a connected main aisle clear',
        'bundles': [{'recipe': recipe, 'minimum': 1, 'recommended': n, 'maximum': n+1,
                     'seats_per_group': seats, 'reason': 'Serve occupants with complete groups'}]}, function)


def obj(key, category, x, y, group='work', rotation=0):
    return InteriorObject(key, 'r', category, 'procedural::'+category, Point2D(x,y),
                          1.4 if category=='desk' else .5, .7 if category=='desk' else .5,
                          .8, rotation, metadata={'group_key':group, 'front_axis':'+Y'})


class FunctionalConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.room=Room('r','Open workspace','open_office',Bounds2D(0,0,8,7))

    def test_hard_authority_and_invalid_counts_cannot_be_injected(self):
        p=plan();raw={k:p[k] for k in ('reason','bundles','intentional_open_space')}
        for field,value in [('user_minimum',0),('required_inventory',[])]:
            with self.assertRaises(ValueError):validate_plan({**raw,field:value},'open_office')
        for field,value in [('minimum',4),('maximum',2),('recommended',True),('seats_per_group',6)]:
            bad=deepcopy(raw);bad['bundles'][0][field]=value
            with self.assertRaises(ValueError):validate_plan(bad,'open_office')
        self.assertFalse(p['capacity_certified']);self.assertIn('advisory',p['authority'])

    def test_primary_activity_and_object_budget(self):
        with self.assertRaises(ValueError):plan(recipe='documents',seats=0)
        with self.assertRaises(ValueError):plan('meeting_room','meeting',n=4,seats=8)

    def test_complete_bundles_not_scalar_density(self):
        self.assertEqual(target_inventory(plan()),{'desk':3,'office_chair':3})
        self.assertEqual(target_inventory(plan('restaurant','dining',2,4)),{'dining_table':2,'dining_chair':8})
        self.assertEqual(target_inventory(plan('living_room','lounge',1,0)),{'sofa':1,'coffee_table':1})

    def test_loose_distant_and_backward_chairs_do_not_count_as_work_capacity(self):
        desk=obj('desk','desk',3,3);chair=obj('chair','office_chair',3,2)
        measure=lambda chair:evaluate_configuration(self.room,[desk,chair],plan())['bundles'][0]['complete_groups']
        self.assertEqual(measure(chair),1)
        self.assertEqual(measure(replace(chair,rotation_deg=180)),0)
        self.assertEqual(measure(replace(chair,position=Point2D(3,0))),0)
        self.assertEqual(measure(replace(chair,metadata={})),0)

    def test_chairs_are_not_counted_twice_between_tables(self):
        p=plan('restaurant','dining',2,2)
        objects=[obj('t1','dining_table',3,3),obj('t2','dining_table',3.2,3),
                 obj('s1','dining_chair',3,2),obj('s2','dining_chair',3.2,2)]
        self.assertEqual(evaluate_configuration(self.room,objects,p)['bundles'][0]['paired_seats'],2)

    def test_spare_chairs_at_another_table_do_not_fill_one_groups_gap(self):
        p=plan('restaurant','dining',2,4)
        tables=[obj('t1','dining_table',2,3,group='a'),obj('t2','dining_table',6,3,group='b')]
        chairs=[obj('c'+str(i),'dining_chair',t.position.x+(i%3-1)*0.1,2,
                    group=t.metadata['group_key']) for i,t in enumerate([tables[0]]*6+[tables[1]]*2)]
        measured=evaluate_configuration(self.room,tables+chairs,p)
        self.assertEqual(measured['bundles'][0]['paired_seats'],8)
        self.assertEqual(measured['bundles'][0]['seat_gap'],2)
        self.assertFalse(measured['recommendation_met'])

    def test_smaller_complete_dining_groups_can_improve_without_claiming_target_met(self):
        p=plan('restaurant','dining',3,4)
        first=[obj('t1','dining_table',3,3,group='a'),obj('c1','dining_chair',2.8,2,group='a'),
               obj('c2','dining_chair',3.2,2,group='a')]
        second=[obj('t2','dining_table',6,3,group='b'),obj('c3','dining_chair',5.8,2,group='b'),
                obj('c4','dining_chair',6.2,2,group='b')]
        before=evaluate_configuration(self.room,first,p);after=evaluate_configuration(self.room,first+second,p)
        self.assertGreater(after['fulfilled_group_targets'],before['fulfilled_group_targets'])
        self.assertEqual(after['bundles'][0]['paired_seats'],4)
        self.assertFalse(after['recommendation_met']);self.assertEqual(after['bundles'][0]['seat_gap'],8)

    def test_reference_fallback_retains_inventory_and_does_not_drop_support_dressing(self):
        from cityg.planning.functional_configuration_references import configuration_references
        from collections import Counter
        objs=[obj('desk','desk',3,3),obj('chair','office_chair',3,2),obj('book','bookcase',6,3)]
        programs=list(configuration_references(self.room,objs,plan()))
        self.assertTrue(programs);self.assertLessEqual(len(programs),8)
        for _,p in programs:
            counts=Counter(x['category']for g in p.design.groups for x in [g['anchor'],*g['members']])
            self.assertGreaterEqual(counts['bookcase'],1)
            self.assertGreaterEqual(counts['desk'],1);self.assertGreaterEqual(counts['office_chair'],1)
        self.room.metadata['room_design']={'surface_items':[{'id':'keep_monitor'}]}
        self.assertEqual(list(configuration_references(self.room,objs,plan())),[])

    def test_metric_pairing_does_not_use_scaled_canonical_boxes(self):
        desk=obj('desk','desk',30,30);chair=obj('chair','office_chair',30,20)
        desk.metadata['metric_room_placement']={'center':[3,3],'dimensions_m':[1.4,.7,.8]}
        chair.metadata['metric_room_placement']={'center':[3,2],'dimensions_m':[.5,.5,.8]}
        before=deepcopy([desk,chair])
        self.assertEqual(evaluate_configuration(self.room,[desk,chair],plan())['bundles'][0]['complete_groups'],1)
        self.assertEqual([desk,chair],before)

    def test_disabled_stage_returns_same_city_without_calls(self):
        from cityg.refinement.functional_configuration import improve_functional_configuration
        city=object()
        result,report=improve_functional_configuration(city,object(),None,None)
        self.assertIs(result,city);self.assertEqual(report['attempts'],[])

    def test_optional_stage_failure_preserves_geometry_and_reports_unmet_goal(self):
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec
        from cityg.refinement.functional_configuration import improve_functional_configuration
        city=BaselineCityPlanner().plan(CitySpec(building_count=1))
        b=next(city.iter_buildings());f=b.floors[0];r=next(r for r in f.rooms if r.function!='corridor')
        for q in f.rooms:q.function='storage'
        r.function='open_office';old=deepcopy(city)
        with patch('cityg.refinement.functional_configuration.propose_configuration',return_value=(plan(),())), \
             patch('cityg.refinement.functional_configuration.prepare_preflight',side_effect=ValueError('No space')):
            result,report=improve_functional_configuration(city,object(),None,None,
                config={'enabled':True,'max_rooms':1},target_levels={b.id:[f.level]})
        self.assertEqual(city,old)
        self.assertEqual(report['attempts'][0]['status'],'not_improved_previous_room_preserved')
        rr=next(q for q in result.iter_rooms() if q.id==r.id)
        self.assertEqual(rr.bounds,r.bounds);self.assertEqual(list(result.iter_objects()),list(city.iter_objects()))
        self.assertEqual(report['floor_feedback'][0]['authority'],'advisory')
        self.assertFalse(report['compiled_rooms'])

    def test_invalid_options_rejected(self):
        for value in ({'max_rooms':0},{'enabled':1},{'placement_calls':50},{'density':.5}):
            with self.assertRaises(ValueError):options(value)

    def test_unselected_and_protected_rooms_never_call_model(self):
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec
        from cityg.refinement.functional_configuration import improve_functional_configuration
        city=BaselineCityPlanner().plan(CitySpec(building_count=1));b=next(city.iter_buildings())
        for r in city.iter_rooms():r.function='open_office';r.metadata['protected']=True
        with patch('cityg.refinement.functional_configuration.propose_configuration',side_effect=AssertionError('must not plan')):
            for targets in ({},{b.id:[0]}):
                _,report=improve_functional_configuration(city,object(),None,None,
                    config={'enabled':True},target_levels=targets)
                self.assertFalse(report['attempts'])

    def test_hard_shortfall_skips_optional_work(self):
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec
        from cityg.refinement.functional_configuration import improve_functional_configuration
        from test_interior_requirements import requirement
        city=BaselineCityPlanner().plan(CitySpec(building_count=1));b=next(city.iter_buildings())
        r=b.floors[0].rooms[0];r.function='open_office'
        row=requirement();row.update(building_id=b.id,area_m2=b.footprint.area,
                                     required_functions=['open_office'])
        row['inventory']=[{'room_function':'open_office','category':'desk','min_count':1000}]
        b.metadata['interior_layout_contract']={'requirements':[row]}
        with patch('cityg.refinement.functional_configuration.propose_configuration',side_effect=AssertionError('must not plan')):
            _,report=improve_functional_configuration(city,object(),None,None,
                config={'enabled':True},target_levels={b.id:[0]})
        self.assertTrue(report['attempts'])
        self.assertTrue(all(a['status']=='skipped_hard_requirements_unmet'for a in report['attempts']))

    def test_final_publication_uses_latest_certificate_without_disabling_checks(self):
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec
        from cityg.planning.generation_prototypes import GenerationPrototypes
        from tempfile import TemporaryDirectory
        from pathlib import Path
        city=BaselineCityPlanner().plan(CitySpec(building_count=1));b=next(city.iter_buildings());f=b.floors[0];rid=f.rooms[0].id
        for floor in city.iter_floors():floor.objects=[]
        report={'rooms':[], 'authorized_levels':{b.id:[0]},
                'functional_completion':{'max_rooms':1,'compiled_rooms':[{'room_id':rid,'source':'functional_completion','compiled_verified':True,'major_count':2}]},
                'functional_configuration':{'max_rooms':1,'compiled_rooms':[{'room_id':rid,'source':'functional_configuration','compiled_verified':True,'major_count':6}]}}
        with TemporaryDirectory() as tmp, \
             patch('cityg.geometry.incremental.scene_from_manifest',return_value=object()), \
             patch('cityg.planning.generation_prototypes.verify_room',return_value=[]) as verify:
            p=Path(tmp)/'manifest.json';p.write_text('{}')
            result=GenerationPrototypes.verify_final(city,p,report)
            self.assertTrue(result['ok']);self.assertEqual(verify.call_count,1)
            self.assertEqual(verify.call_args.args[-1]['major_count'],6)
            report['functional_configuration']['compiled_rooms'][0]['compiled_verified']=False
            with self.assertRaises(ValueError):GenerationPrototypes.verify_final(city,p,report)


if __name__=='__main__':unittest.main()
