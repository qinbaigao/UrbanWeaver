from dataclasses import replace
import unittest

from tests.test_tower_site_coordination import fixture
from cityg.interior_requirements import evaluate_requirements
from cityg.planning.seating_contract import seating_contracts, check_seating


def requirement(building_id, level, quote):
    common = {'room_function':'meeting_room'}
    return {'building_id':building_id, 'levels':[level], 'source_quote':quote, 'label':'meeting',
            'area_basis':'floor_gross','area_m2':None,'required_functions':['meeting_room'],
            'inventory':[{**common,'category':'meeting_table','min_count':1,'count_basis':'presence'},
                         {**common,'category':'meeting_chair','min_count':6,'count_basis':'explicit_number'}]}


class SingleTableTests(unittest.TestCase):
    def test_reversed_and_split_seating_not_certified_by_totals(self):
        from cityg.planning.room_metric_frame import bind_metric_object,restore_metric_object
        from cityg.planning.room_envelope import metric_envelope
        city,b,f,r=fixture('meeting_area')
        row=requirement(b.id,f.level,'Provide a meeting area with a table and seating for six.')
        self.assertEqual(evaluate_requirements(city,[row])[0]['status'],'satisfied')
        env=metric_envelope(b,f,r)
        i=next(i for i,o in enumerate(f.objects) if o.category=='meeting_chair')
        obj=restore_metric_object(f.objects[i],b,f,r,env)
        obj.rotation_deg=(obj.rotation_deg+180)%360
        bind_metric_object(obj,b,f,r,env)
        f.objects[i]=obj
        failed=evaluate_requirements(city,[row])[0]
        self.assertEqual(failed['inventory_shortfalls'],[])
        self.assertEqual(failed['status'],'violated')
        self.assertEqual(failed['single_table_seating'][0]['rooms'][0]['paired_at_one_table'],5)
        obj.rotation_deg=(obj.rotation_deg+180)%360
        other=next(q for q in f.rooms if q.function=='break_room')
        other.function='meeting_room'
        f.objects[i]=replace(obj,room_id=other.id)
        self.assertEqual(evaluate_requirements(city,[row])[0]['status'],'violated')

    def test_aggregate_quantities_do_not_impose_one_table(self):
        row=requirement('b',0,'Distribute six meeting chairs and two tables across the meeting rooms.')
        self.assertEqual(list(seating_contracts(row)),[])

    def test_four_seats_in_quoted_dining_area_only(self):
        row=requirement('b',0,'A dining area with a table and four seats, and a meeting room with a board.')
        dining=[{'category':'dining_table','room_function':'living_room','min_count':1,'count_basis':'presence'},
                {'category':'dining_chair','room_function':'living_room','min_count':4,'count_basis':'explicit_number'}]
        row['inventory'][1]['min_count']=4
        row['inventory'].extend(dining)
        self.assertEqual([(q['anchor'],q['required']) for q in seating_contracts(row)],[('dining_table',4)])

    def test_room_gate_uses_the_same_walkable_bounds_as_placement(self):
        from unittest.mock import patch
        from cityg.planning.room_envelope import metric_envelope
        from cityg.planning.room_constraints import circulation_check, ROOM_WALL_INSET_M
        city,b,f,r=fixture('meeting_area')
        row=requirement(b.id,f.level,'Provide a meeting area with seating for six.')
        contract,=seating_contracts(row)
        env=metric_envelope(b,f,r)
        with patch('cityg.planning.seating_contract.circulation_check',wraps=circulation_check) as checker:
            self.assertTrue(check_seating(b,f,contract)['ok'])
        self.assertEqual(checker.call_args.args[3],env['room'].bounds.inset(ROOM_WALL_INSET_M))

    def test_no_door_cannot_certify_single_table_access(self):
        city,b,f,r=fixture('meeting_area')
        row=requirement(b.id,f.level,'提供六人会议室。')
        contract,=seating_contracts(row)
        f.doors=[d for d in f.doors if r.id not in (d.room_a_id,d.room_b_id)]
        self.assertFalse(check_seating(b,f,contract)['ok'])
