import unittest
from copy import deepcopy
from types import SimpleNamespace
from cityg.interior_requirements import (validate_requirements,bind_requirements,
    constrain_reservations,evaluate_requirements)
from cityg.schemas import Bounds2D, Room, Floor, Building, Point2D
from cityg.planning.interior_capacity_search import improve_reserved_capacity
from cityg.planning.furnishing_sufficiency import assess_furnishing


def requirement(label='A',area=160):
    return dict(label=label,source_quote='A ground floor 160 m2 office with 2 desks.',
                building_id=None,building_function='commercial',levels=[0],area_m2=area,
                area_basis='floor_gross',required_functions=['office'],
                inventory=[dict(room_function='office',category='desk',min_count=2)])


def fixture():
    buildings=[Building(f'building_{i:03d}',f'b{i}','commercial',Bounds2D(i*50,0,i*50+30,30),
        Point2D(i*50,15),floors=[Floor(f'f{i}',0,0,3,rooms=[Room(f'r{i}','office','office',Bounds2D(0,0,10,10))])]) for i in range(2)]
    city=SimpleNamespace(iter_buildings=lambda:iter(buildings),
        iter_objects=lambda:(o for b in buildings for f in b.floors for o in f.objects))
    targets={b.id:dict(circulation_axis='x',entrance_side='west',source='new_scene_rectangular_interior_v1') for b in buildings}
    return city,buildings,targets


class InteriorRequirementsTests(unittest.TestCase):
    def test_two_labels_bind_distinctly_and_keep_area_after_capacity_search(self):
        city,buildings,targets=fixture(); rows=[requirement(),requirement('B',240)]
        bindings=bind_requirements(city,rows);constrain_reservations(city,targets,bindings)
        result,report=improve_reserved_capacity(None,SimpleNamespace(room_count_strategy='adaptive'),targets,{},None)
        self.assertEqual(result,targets)
        self.assertEqual([r['status'] for r in report['buildings']],['explicit_area_preserved']*2)
        for b,area in zip(buildings,[160,240]):
            fp=Bounds2D(**result[b.id]['footprint'])
            self.assertAlmostEqual(fp.area,area);self.assertTrue(b.footprint.contains_bounds(fp))
            self.assertEqual(fp.min_x,b.footprint.min_x)

    def test_north_frontage_and_excess_area_and_net_are_not_silently_changed(self):
        city,buildings,targets=fixture();b=buildings[0]
        targets[b.id].update(circulation_axis='y',entrance_side='north')
        constrain_reservations(city,targets,bind_requirements(city,[requirement()]))
        fp=Bounds2D(**targets[b.id]['footprint']);self.assertAlmostEqual(fp.area,160)
        self.assertEqual(fp.max_y,b.footprint.max_y)
        for row in [requirement(area=1000),{**requirement(),'area_basis':'rooms_net'}]:
            with self.assertRaises(ValueError):constrain_reservations(city,targets,bind_requirements(city,[row]))

    def test_quotes_and_function_inventory_binding(self):
        row=requirement();validate_requirements([row],instruction=row['source_quote'])
        with self.assertRaisesRegex(ValueError,'quote'):validate_requirements([row],instruction='different')
        bad=deepcopy(row);bad['inventory'][0]['room_function']='shop'
        with self.assertRaisesRegex(ValueError,'inventory'):validate_requirements([bad])

    def test_same_building_multilevel_binding_and_cache_distinguishes_requirements(self):
        from cityg.agents.building_floor import BuildingFloorAgent
        city,buildings,targets=fixture();b=buildings[0];b.floors.append(Floor('f2',1,3,3))
        row2={**requirement(),'levels':[1]}
        bindings=bind_requirements(city,[requirement(),row2]);self.assertEqual(list(bindings),[b.id])
        old=BuildingFloorAgent.signature(b)
        b.metadata['interior_layout_contract']={'requirements':bindings[b.id]}
        self.assertNotEqual(old,BuildingFloorAgent.signature(b))
        bad={**requirement(),'building_id':'building_999'}
        with self.assertRaises(ValueError):bind_requirements(city,[bad])

    def test_actual_inventory_and_area_not_declared_program(self):
        city,buildings,targets=fixture();bindings=bind_requirements(city,[requirement()])
        rows=bindings[buildings[0].id]
        result=evaluate_requirements(city,rows)[0]
        self.assertEqual(result['status'],'violated');self.assertGreater(result['relative_area_error'],1)
        self.assertEqual(result['inventory_shortfalls'][0]['placed'],0)
        buildings[0].footprint=Bounds2D(0,0,16,10)
        f=buildings[0].floors[0]
        f.objects=[SimpleNamespace(room_id='r0',category='desk') for _ in range(2)]
        self.assertEqual(evaluate_requirements(city,rows)[0]['status'],'satisfied')
        # Extra objects in another room function never fill an office requirement.
        f.rooms.append(Room('shop','shop','shop',Bounds2D(0,0,4,4)))
        f.objects[1].room_id='shop'
        self.assertEqual(evaluate_requirements(city,rows)[0]['inventory_shortfalls'][0]['placed'],1)

    def test_actual_planner_preserves_requested_area_and_other_buildings(self):
        from test_interior_capability import InteriorCapabilityTests
        from cityg.planning.interior_capability import reserve_interiors
        from cityg.planning.programmed import ProgrammedCityPlanner
        from cityg.planning.generation_prototypes import DeferredFurniture
        from cityg.validation import CityValidator
        spec,program,draft=InteriorCapabilityTests().fixture()
        targets,pins,_=reserve_interiors(draft,limit=1)
        bid=next(iter(targets)); b=next(b for b in draft.iter_buildings() if b.id==bid)
        row=requirement();row.update(building_id=bid,building_function=b.function,
                                     required_functions=[],inventory=[])
        constrain_reservations(draft,targets,bind_requirements(draft,[row]))
        result=ProgrammedCityPlanner(program,floor_detail_agent=DeferredFurniture(),
                                    interior_targets=targets,archetype_pins=pins).plan(spec)
        actual=next(b for b in result.iter_buildings() if b.id==bid)
        self.assertAlmostEqual(actual.footprint.area,160)
        self.assertTrue(CityValidator().validate(result).ok)
        old={b.id:b for b in draft.iter_buildings()}
        for building in result.iter_buildings():
            if building.id!=bid:
                original=old[building.id]
                self.assertEqual((building.footprint,building.entrance,building.floors,building.vertical_connectors),
                                 (original.footprint,original.entrance,original.floors,original.vertical_connectors))
                self.assertEqual(building.metadata['archetype_id'],original.metadata['archetype_id'])

    def test_named_new_buildings_can_use_eligible_carriers_but_ids_do_not_change(self):
        city,buildings,_=fixture()
        bindings=bind_requirements(city,[requirement()],eligible_ids={'building_001'})
        self.assertEqual(list(bindings),['building_001'])
        row={**requirement(),'building_id':'building_000'}
        self.assertEqual(list(bind_requirements(city,[row],eligible_ids={'building_001'})),['building_000'])

    def test_functional_completion_commits_city_and_does_not_repeat_failed_rooms(self):
        from unittest.mock import patch
        from cityg.refinement.functional_completion import complete_inventory
        city,buildings,targets=fixture(); rows=bind_requirements(city,[requirement()])
        b=buildings[0];b.metadata['interior_layout_contract']={'requirements':rows[b.id]}
        b.footprint=Bounds2D(0,0,16,10)
        def commit(current,rid,program,**kwargs):
            b.floors[0].objects=[SimpleNamespace(room_id=rid,category='desk') for _ in range(2)]
            return SimpleNamespace(city=current,report={'compiled_gate':{'ok':True,'room_checks':[]}}),{}
        with patch('cityg.refinement.room.RoomProgramAgent') as agent, \
             patch('cityg.refinement.room_preflight.prepare_preflight',return_value=({},None,None)), \
             patch('cityg.refinement.room_commit.commit_room_program',side_effect=commit):
            agent.return_value.propose.return_value=SimpleNamespace(attempts=(),program=None,raw={})
            result,report=complete_inventory(city,None,None,None,max_rooms=2)
            self.assertIs(result,city)
            self.assertEqual(len(report['attempts']),1)
            self.assertEqual(report['after'][0]['status'],'satisfied')
        b.floors[0].objects=[]
        with patch('cityg.refinement.room.RoomProgramAgent') as agent, \
             patch('cityg.refinement.room_preflight.prepare_preflight',return_value=({},None,None)):
            agent.return_value.propose.side_effect=ValueError('cannot place')
            _,report=complete_inventory(city,None,None,None,max_rooms=5)
            self.assertEqual(len(report['attempts']),1)
            self.assertEqual(report['after'][0]['status'],'violated')

    def test_final_publication_checks_completion_budget_scope_and_unplanned_objects(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from cityg.planning.generation_prototypes import GenerationPrototypes
        city,buildings,_=fixture()
        buildings[0].floors[0].objects=[SimpleNamespace(room_id='r0',category='desk')]
        supplement={'room_id':'r0','compiled_verified':True,'source':'functional_completion',
                    'major_count':1,'expected_inventory':{}}
        report={'rooms':[],'authorized_levels':{'building_000':[0]},
                'functional_completion':{'max_rooms':1,'compiled_rooms':[supplement]}}
        with tempfile.TemporaryDirectory() as directory, \
             patch('cityg.geometry.incremental.scene_from_manifest',return_value=None), \
             patch('cityg.planning.generation_prototypes.verify_room',return_value=[]):
            path=Path(directory)/'manifest.json';path.write_text('{}')
            self.assertTrue(GenerationPrototypes.verify_final(city,path,report)['ok'])
            bad=deepcopy(report);bad['functional_completion']['max_rooms']=0
            with self.assertRaisesRegex(ValueError,'budget'):GenerationPrototypes.verify_final(city,path,bad)
            bad=deepcopy(report);bad['authorized_levels']={}
            with self.assertRaisesRegex(ValueError,'scope'):GenerationPrototypes.verify_final(city,path,bad)
            buildings[1].floors[0].objects=[SimpleNamespace(room_id='r1',category='desk')]
            with self.assertRaisesRegex(ValueError,'Unplanned'):GenerationPrototypes.verify_final(city,path,report)

    def test_primary_function_and_large_room_sparsity(self):
        room=Room('r','office','office',Bounds2D(0,0,30,30))
        objects=[SimpleNamespace(id=str(i),room_id='r',category='office_chair',metadata={},width_m=.5,depth_m=.5) for i in range(20)]
        result=assess_furnishing(room,objects)
        self.assertIn('missing_primary_functional_bundle',result['reasons'])
        self.assertIn('low_furniture_footprint_for_available_area',result['reasons'])

if __name__=='__main__':unittest.main()
