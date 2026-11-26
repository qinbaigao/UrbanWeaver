import unittest
from types import SimpleNamespace

from cityg.planning.furnishing_acceptance import coverage, room_service
from tests.test_tower_site_coordination import fixture


class FurnishingAcceptanceTests(unittest.TestCase):
    def test_service_requires_realized_inventory_and_door_access(self):
        _, building, floor, room = fixture('meeting_area')
        self.assertTrue(room_service(building, floor, room, [])['ok'])
        result = room_service(building, floor, room, [{'category':'meeting_chair','min_count':7}])
        self.assertEqual(result['missing'], {'meeting_chair':1})
        floor.doors = [d for d in floor.doors if room.id not in (d.room_a_id, d.room_b_id)]
        self.assertFalse(room_service(building, floor, room, [])['ok'])

    def test_supplement_can_replace_missing_reference_but_must_cover_named_buildings(self):
        buildings = [SimpleNamespace(id=bid,metadata={'interior_layout_contract':{'requirements':[1]}})
                     for bid in ('A', 'B')]
        city = SimpleNamespace(iter_buildings=lambda:iter(buildings))
        report = {'rooms':[{'room_id':'r1'}],'options':{'max_rooms':2},'authorized_levels':{'A':[0],'B':[0]}}
        rows = [{'room_id':'r1','building_id':'A','service':{'ok':True}},
                {'room_id':'r2','building_id':'B','service':{'ok':True}}]
        result = coverage(report, rows, city)
        self.assertEqual((result['prototype_rooms'], result['verified_rooms']), (1, 2))
        self.assertTrue(result['target_met'])
        rows[1]['building_id'] = 'A'
        self.assertFalse(coverage(report, rows, city)['target_met'])
        rows[1]['building_id'] = 'B'
        rows[0]['service']['ok'] = False
        self.assertFalse(coverage(report, rows, city)['target_met'])
