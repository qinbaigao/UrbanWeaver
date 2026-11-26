from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from cityg.design_goals import validate_goals,goal_context,extract_goals
from cityg.planning.prototypes import LayoutPrototypeLibrary
from cityg.planning.reference_variations import personalize_design,EMPTY_ADJUSTMENTS,asset_options
from cityg.planning.prototype_adaptation import rotated_design

ROOT=Path(__file__).resolve().parents[1]


class GoalVariationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.lib=LayoutPrototypeLibrary(ROOT/'configs/layout_prototypes/v1')

    def test_exact_quotes_soft_authority_and_hierarchy_scope(self):
        goal={'source_quote':'协作办公','preference':'保留共同工作区','levels':['floor','room']}
        rows=validate_goals({'goals':[goal]},'需要协作办公')
        self.assertEqual(rows[0]['status'],'unverified')
        self.assertEqual(goal_context(rows,'building'),[])
        self.assertEqual(goal_context(rows,'building_floor'),rows)
        self.assertEqual(rows,validate_goals({'goals':[goal]},'需要协作办公'))
        for wrong in ({**goal,'source_quote':'必须十个工位'},{**goal,'levels':['wrong']},
                      {**goal,'preference':''}):
            with self.assertRaises(ValueError): validate_goals({'goals':[wrong]},'需要协作办公')

    def test_goal_service_failure_is_not_semantic_success(self):
        class Service:
            def complete(self,*args): return '{"goals":[{"invented":true}]}'
        report,attempts=extract_goals(Service(),'办公室',max_calls=2)
        self.assertEqual(len(attempts),2);self.assertEqual(report['status'],'unavailable')
        self.assertEqual(report['goals'],[]);self.assertFalse(report['semantic_satisfaction_proven'])

    def test_add_work_group_preserves_original_inventory_and_surface_support_ids(self):
        proto=self.lib.materialize('office_private_v1');old=deepcopy(proto)
        edits={**deepcopy(EMPTY_ADJUSTMENTS),'group_copies':[
            {'source_group_id':'work','new_group_id':'work_extra','zone_id':'work'}]}
        result=personalize_design(proto,edits,self.lib,{'max_group_copies':1})
        self.assertEqual(proto,old)
        self.assertEqual(len(result.design.groups),len(proto.design.groups)+1)
        self.assertEqual(result.asset_bindings,proto.asset_bindings)
        ids={i['id'] for g in result.design.groups for i in [g['anchor'],*g['members']]}
        self.assertTrue(all(q['support_member_id'] in ids for q in result.design.surface_items))
        before={i['category']:i['minimum'] for i in proto.design.furnishing_brief['items']}
        after={i['category']:i['minimum'] for i in result.design.furnishing_brief['items']}
        self.assertTrue(all(after[k]>=n for k,n in before.items()))
        with self.assertRaises(ValueError): personalize_design(proto,edits,self.lib,{})
        edits['group_copies'][0]['new_group_id']='../escape'
        with self.assertRaises(ValueError): personalize_design(proto,edits,self.lib,{'max_group_copies':1})

    def test_zone_position_rotates_once_and_protected_zone_refuses(self):
        proto=self.lib.materialize('office_private_v1')
        edits={**deepcopy(EMPTY_ADJUSTMENTS),'zone_positions':[{'zone_id':'work','position':'south'}]}
        changed=personalize_design(proto,edits,self.lib,{'max_zone_moves':1})
        world=rotated_design(changed,1)
        self.assertEqual(next(g for g in world.design.groups if g['id']=='work')['placement']['wall'],'east')
        protected=replace(proto,design=replace(proto.design,protected_groups=('work',)))
        with self.assertRaises(ValueError): personalize_design(protected,edits,self.lib,{'max_zone_moves':1})

    def test_asset_admissibility_and_no_arbitrary_mesh(self):
        proto=self.lib.materialize('office_private_v1')
        offered=asset_options(proto,self.lib)
        self.assertTrue(all(proto.asset_bindings[k] in values for k,values in offered.items()))
        edits={**deepcopy(EMPTY_ADJUSTMENTS),'asset_choices':[{'category':'desk','asset_id':'outdoor_car'}]}
        with self.assertRaises(ValueError): personalize_design(proto,edits,self.lib,{'max_asset_changes':1})

    def test_copy_does_not_drop_required_cross_group_relations(self):
        from cityg.planning.room_design import RoomDesign
        from cityg.planning.interiors import ASSET_CATALOG
        proto=self.lib.materialize('office_private_v1')
        data=proto.design.to_dict()
        data['group_relations']=[{'subject':'work','target':'storage','relation':'near',
                                 'min_distance_m':0,'max_distance_m':8,'required':True}]
        proto=replace(proto,design=RoomDesign.from_dict(data,ASSET_CATALOG))
        edits={**deepcopy(EMPTY_ADJUSTMENTS),'group_copies':[
            {'source_group_id':'work','new_group_id':'work_extra','zone_id':'work'}]}
        with self.assertRaisesRegex(ValueError,'cross-group'):
            personalize_design(proto,edits,self.lib,{'max_group_copies':1})

    def test_semantic_variants_in_compatible_offices_pass_real_compile(self):
        from cityg.assets import AssetRegistry
        from cityg.ccwp import build_world_program
        from cityg.geometry import GeometryCompiler
        from cityg.planning.generation_prototypes import GenerationPrototypes,load_options
        from cityg.planning.prototype_lab import make_lab
        from cityg.planning.prototype_adaptation import room_candidates,populate_adapted_room
        from cityg.planning.city_prototype_adapter import verify_room
        runtime=GenerationPrototypes(load_options(ROOT/'configs/generation_prototypes.json'))
        variants=[('office_private_v1',5.2,5.2,5,
                   {**deepcopy(EMPTY_ADJUSTMENTS),'zone_positions':[
                       {'zone_id':'visitors','position':'east'},{'zone_id':'storage','position':'west'}]}),
                  ('office_four_v1',9,7.5,13,
                   {**deepcopy(EMPTY_ADJUSTMENTS),'group_copies':[
                       {'source_group_id':'work_a','new_group_id':'work_extra','zone_id':'north'}]}),
                  ('office_private_v1',5.2,5.2,5,deepcopy(EMPTY_ADJUSTMENTS))]
        for key,width,depth,count,edits in variants:
            with self.subTest(key=key):
                case={**self.lib.rooms[key]['reference'],'width_m':width,'depth_m':depth}
                city,targets=make_lab(self.lib,[key],{key:case});_,b,f,r=targets[0]
                compiler=GeometryCompiler(asset_registry=AssetRegistry(ROOT/'assets/asset_registry.json'))
                registry=runtime.prepare_resources(compiler.asset_registry,compiler)
                candidate=room_candidates(self.lib,b,f,r)[0]
                row=populate_adapted_room(city,b,f,r,self.lib,registry,candidate,review_only=True,
                    personalization=[{'member_id':'work_chair','gap_scale':1.0}] if key=='office_private_v1' else [],
                    design_adjustments=edits,design_limits={'max_zone_moves':2,'max_group_copies':1})
                city.world_program=build_world_program(city,producer='variation_test',seed=17)
                checks=verify_room(compiler.compile(city),b,f,r,row)
                self.assertTrue(all(c['ok'] for c in checks))
                self.assertEqual(row['major_count'],count)
                self.assertEqual(row['design_adjustments'],edits)
                changed=any(edits.values())
                self.assertEqual(row['design_changed'],changed)
                self.assertEqual(row['effective_fingerprint']!=row['reference_effective_fingerprint'],changed)


if __name__=='__main__': unittest.main()
