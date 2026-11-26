import json
from copy import deepcopy
import unittest

from cityg.edit_constraints import explicit_edit_constraints, check_edit_constraints, validate_edit_plan_constraints
from cityg.editing import EditAgent
from cityg.subtree_transactions import _details_spec, FloorSubtreePlanner
from test_editing import _city


class EditConstraintTests(unittest.TestCase):
    def test_building_counts_are_target_bound_and_checked_after_edit(self):
        city=_city();building=next(city.iter_buildings())
        instruction=f'将 id={building.id} 重建为严格3层，每层4个非走廊房间'
        constraints=explicit_edit_constraints(city,instruction)
        self.assertEqual({c['kind']:c['expected'] for c in constraints},
                         {'building_floor_count':3,'building_rooms_per_floor':4})
        good={'status':'replan_required','replan_requests':[{
            'kind':'building_subtree','target_id':building.id,
            'details':json.dumps({'floor_count':3,'room_count':4})}]}
        validate_edit_plan_constraints(good,constraints)
        self.assertFalse(check_edit_constraints(city,constraints)['ok'])
        wrong=deepcopy(good)
        wrong['replan_requests'][0]['details']='{"floor_count": 3}'
        with self.assertRaisesRegex(ValueError,'room_count=4'):
            validate_edit_plan_constraints(wrong,constraints)
        from cityg.subtree_transactions import BuildingSubtreePlanner
        result=BuildingSubtreePlanner().replace(city,building.id,{'floor_count':3,'room_count':4})
        self.assertTrue(check_edit_constraints(result.city,constraints)['ok'])

    def test_unsupported_building_count_is_refused_before_model(self):
        city=_city();building=next(city.iter_buildings())
        class Service:
            def complete(self,*args): raise AssertionError('Do not ask the model to lower an explicit count')
        for instruction in (f'将 id={building.id} 改为10000层',
                            f'将 id={building.id} 改为0层',
                            f'将 id={building.id} 重建为3层，每层10000个房间'):
            result=EditAgent(Service()).plan(city,instruction)
            self.assertEqual(result.status,'needs_clarification')
            self.assertFalse(result.operations)

    def test_non_corridor_count_and_target_over_current_count(self):
        for text in ('改为严格4个非走廊房间，当前6个房间',
                     'Currently 6 rooms; repartition to strictly 4 non-corridor rooms',
                     'Redesign to contain exactly 4 separate rooms', '严格4间非走廊办公室'):
            self.assertEqual(_details_spec(text)['room_count'],4,text)

    def test_multi_floor_shared_and_separate_counts(self):
        city=_city();a,b=list(city.iter_floors())[:2]
        for text in (f'将 id={a.id} 和 id={b.id} 重新分区，每层严格4个非走廊房间',
                     f'Repartition {a.id} and {b.id} to 4 non-corridor rooms each floor.'):
            constraints=explicit_edit_constraints(city,text)
            self.assertEqual({c['entity_id']:c['expected'] for c in constraints},{a.id:4,b.id:4})
        constraints=explicit_edit_constraints(city,f'id={a.id} 改为4个房间；id={b.id} 改为5个房间')
        self.assertEqual({c['entity_id']:c['expected'] for c in constraints},{a.id:4,b.id:5})
        with self.assertRaises(ValueError):
            explicit_edit_constraints(city,f'{a.id} 和 {b.id} 共4个房间')
        with self.assertRaises(ValueError):
            validate_edit_plan_constraints({'status':'replan_required','replan_requests':[
                {'kind':'floor_layout','target_id':a.id,'details':'room_count=4'}]},constraints)

    def test_omitted_bindings_recover_all_explicit_targets_only(self):
        city=_city();a,b=list(city.iter_floors())[:2]
        plan={'status':'replan_required','reason':'partition','clarification':'','targets':[],
              'operations':[],'visual_checks':[], 'replan_requests':[
                  {'kind':'floor_layout','target_id':f.id,'details':'room_count=4'} for f in (a,b)]}
        class Service:
            def complete(self,*args): return json.dumps(plan)
        result=EditAgent(Service()).plan(city,f'{a.id} 和 {b.id} 每层4个非走廊房间')
        self.assertEqual({i for t in result.targets for i in t['resolved_ids']},{a.id,b.id})
        from cityg.agents import AgentGenerationError
        with self.assertRaises(AgentGenerationError):
            EditAgent(Service(),max_attempts=1).plan(city,f'仅 {a.id} 改为4个房间')

    def test_english_thousands_and_office_counts_are_not_lost(self):
        city=_city();floor=next(city.iter_floors())
        for text in ('Redesign the floor to contain 10,000 independent offices.',
                     '改为10000个独立办公室','room_count=10000'):
            self.assertEqual(_details_spec(text)['room_count'],10000)
            with self.assertRaisesRegex(ValueError,'not silently clamped'):
                FloorSubtreePlanner().replace(city,floor.id,details=text)

    def test_unsupported_explicit_count_is_not_sent_to_model_or_mutated(self):
        city=_city();before=deepcopy(city);floor=next(city.iter_floors())
        class Service:
            def complete(self,*args): raise AssertionError('No guessing needed')
        result=EditAgent(Service()).plan(city,f'将 id={floor.id} 改为10000个独立办公室，不得减少数量')
        self.assertEqual(result.status,'needs_clarification')
        self.assertIn('10000',result.clarification);self.assertFalse(result.operations)
        self.assertEqual(city,before)

    def test_literal_rename_cannot_be_replaced_by_profile_regeneration(self):
        city=_city();building=next(city.iter_buildings())
        wrong={'status':'replan_required','reason':'rename','clarification':'',
            'targets':[{'description':building.id,'resolved_ids':[building.id],'confidence':1}],
            'operations':[],'visual_checks':[],
            'replan_requests':[{'kind':'building_profile','target_id':building.id,'details':'rename to 验收楼甲'}]}
        good={**wrong,'status':'apply','replan_requests':[],
            'operations':[{'op':'replace_entity','target_id':building.id,'path':'display_name','value_json':'"验收楼甲"'}]}
        class Service:
            calls=0
            def complete(self,*args):
                self.calls+=1;return json.dumps(wrong if self.calls==1 else good)
        service=Service();instruction=f'仅将 id={building.id} 的显示名称改为“验收楼甲”'
        result=EditAgent(service,max_attempts=2).plan(city,instruction)
        self.assertEqual(len(result.attempts),2)
        self.assertIn('Literal rename',result.attempts[0].error)
        constraints=explicit_edit_constraints(city,instruction)
        self.assertEqual(constraints[0]['expected'],'验收楼甲')
        self.assertFalse(check_edit_constraints(city,constraints)['ok'])
        building.name='验收楼甲'
        self.assertTrue(check_edit_constraints(city,constraints)['ok'])

    def test_valid_count_has_actual_result_postcondition(self):
        city=_city();floor=next(city.iter_floors())
        constraints=explicit_edit_constraints(city,f'把 id={floor.id} 改为8个办公室')
        self.assertEqual(constraints[0]['expected'],8)
        self.assertFalse(check_edit_constraints(city,constraints)['ok'])
