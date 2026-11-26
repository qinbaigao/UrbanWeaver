from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

from cityg.design_goals import validate_goals
from cityg.planning.spatial_layout import solve_spatial_floor
from cityg.planning.spatial_program import FloorSpatialProgram
from cityg.schemas import Bounds2D,Point2D
from cityg.validation.floor_access_contracts import bind_floor_access_contracts,validate_floor_access_contracts
from cityg.validation.model import ValidationReport


class FloorAccessContractTests(unittest.TestCase):
    def test_city_validator_checks_serialized_contract_after_access_edit(self):
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec,ZoneSpec
        from cityg.serialization import city_from_dict,to_primitive
        from cityg.validation.city import CityValidator
        city=BaselineCityPlanner().plan(CitySpec(building_count=2,min_floors=2,max_floors=2,
            rooms_per_floor=5,zones=(ZoneSpec('homes','residential',1.0),)))
        building=next(city.iter_buildings())
        quoted,_=self.fixture();city.metadata['design_goals']=quoted.metadata['design_goals']
        rule=quoted.metadata['floor_access_contracts']['b']['rules'][0]
        bind_floor_access_contracts(city,{building.id:{'objective':{'access_constraints':[rule]}}})
        city=city_from_dict(to_primitive(city));building=next(city.iter_buildings())
        before=CityValidator().validate(city)
        self.assertNotIn('floor_access_requirement_violated',[i.code for i in before.errors])
        floor=building.floors[0]
        anchor,child=[r for r in floor.rooms if r.function!='corridor'][:2]
        anchor.function='bedroom'
        child_door=next(d for d in floor.doors if child.id in (d.room_a_id,d.room_b_id))
        floor.doors=[d for d in floor.doors if child.id not in (d.room_a_id,d.room_b_id)]
        floor.doors.append(replace(child_door,room_a_id=anchor.id,room_b_id=child.id))
        report=CityValidator().validate(city)
        self.assertIn('floor_access_requirement_violated',[i.code for i in report.errors])

    def fixture(self):
        program=FloorSpatialProgram.from_dict({'family':'residential_clusters','spaces':[
            {'key':f'g{i}_{j}','function':'living_room' if j==0 else 'bedroom',
             'target_area_m2':30 if j==0 else 15,'access_via':'circulation' if j==0 else f'g{i}_0',
             'group':f'g{i}'} for i in range(4) for j in range(2)]})
        floor=solve_spatial_floor(program,floor_id='floor_0',level=0,height=3.2,
            footprint=Bounds2D(0,0,18,20),corridor_depth=3,entrance=Point2D(0,10),
            core_bounds=None,min_width=2.4,max_aspect=3.2,max_depth=30)
        building=SimpleNamespace(id='b',function='residential',floors=[floor])
        quote='卧室不能作为其它房间的必经通道'
        goals=validate_goals({'goals':[{'source_quote':quote,'preference':quote,'levels':['room']}]},quote)
        city=SimpleNamespace(id='city',metadata={'design_goals':goals},iter_buildings=lambda:iter([building]))
        rule={'predicate':'not_through_room','function':'bedroom','applicability':'uniform',
              'supporting_goal_ids':[goals[0]['id']]}
        bind_floor_access_contracts(city,{'b':{'objective':{'access_constraints':[rule]}}})
        return city,building

    def test_later_function_change_is_detected_from_actual_graph(self):
        city,b=self.fixture();report=ValidationReport();validate_floor_access_contracts(city,report)
        self.assertTrue(report.ok)
        next(r for r in b.floors[0].rooms if r.function=='living_room').function='bedroom'
        report=ValidationReport();validate_floor_access_contracts(city,report)
        self.assertIn('floor_access_requirement_violated',[i.code for i in report.errors])

    def test_rewriting_original_goal_cannot_manufacture_satisfaction(self):
        city,_=self.fixture()
        city.metadata['design_goals'][0]['preference']='changed after generation'
        report=ValidationReport();validate_floor_access_contracts(city,report)
        self.assertIn('invalid_floor_access_contract',[i.code for i in report.errors])

    def test_unbound_building_cannot_disappear_and_deferred_rules_are_not_generalized(self):
        city,b=self.fixture();city.iter_buildings=lambda:iter([])
        report=ValidationReport();validate_floor_access_contracts(city,report)
        self.assertFalse(report.ok)
        city,b=self.fixture();rule=deepcopy(city.metadata['floor_access_contracts']['b']['rules'][0])
        city.metadata.pop('floor_access_contracts');rule['applicability']='qualified'
        bind_floor_access_contracts(city,{'b':{'objective':{'access_constraints':[rule]}}})
        self.assertNotIn('floor_access_contracts',city.metadata)
