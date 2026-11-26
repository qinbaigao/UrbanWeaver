from copy import deepcopy
import unittest

from cityg.agents.building_floor import BuildingFloorAgent, BuildingFloorProgram
from cityg.planning.floor_brief import geometry_summary, interior_capability, resolve_brief
from cityg.planning.programs import FloorProfile, FloorArchetype
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import CitySpec, Bounds2D, Point2D


class FloorBriefTests(unittest.TestCase):
    def fixture(self):
        spec = CitySpec(name='brief', building_count=1, min_floors=2,max_floors=2,
                        room_count_strategy='adaptive')
        b = next(BaselineCityPlanner().plan(spec).iter_buildings())
        b.footprint = Bounds2D(0,0,40,14); b.entrance = Point2D(0,7)
        b.metadata.update(massing_style='bar',orientation_deg=0, highrise={'enabled':False})
        b.vertical_connectors.clear()
        base = FloorProfile(b.function,'double_loaded_corridor',.18,('living_room',),
            tuple(FloorArchetype(r,8,2,16,30,2.4,('living_room',)) for r in ('ground','typical')))
        zones=[]
        for level, role in [(0,'ground'),(1,'top')]:
            zones.append({'zone_id':role,'start_level':level,'end_level':level,'role':role,
                'use_type':'residential','family':'double_loaded','min_room_width_m':2.4,
                'max_room_depth_m':8,'max_room_aspect_ratio':2.8,
                'spaces':[{'key':f'living_{i}','function':'living_room','weight':1} for i in range(8)]})
        return b,base,spec,{'zones':zones}

    def test_semantic_program_allocates_real_area_and_preserves_source(self):
        b,base,spec,brief=self.fixture(); before=deepcopy(b)
        profile=resolve_brief(brief,b,base,spec)
        BuildingFloorProgram(b.function,profile).validate(b)
        BuildingFloorAgent._check_spatial_feasibility(profile,b,spec)
        self.assertEqual(before,b)
        self.assertEqual(profile.corridor_ratio,base.corridor_ratio)
        self.assertAlmostEqual(sum(s.target_area_m2 for s in profile.vertical_zones[0].spatial_program.spaces),
                               geometry_summary(b,base)['usable_area_m2'])

    def test_hard_area_and_fixed_count_are_never_relaxed(self):
        b,base,spec,brief=self.fixture()
        brief['zones'][0]['spaces'][0]['max_area_m2']=5
        with self.assertRaises(ValueError): resolve_brief(brief,b,base,spec)
        b,base,spec,brief=self.fixture()
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError,'explicit'):
            resolve_brief(brief,b,base,replace(spec,room_count_strategy='fixed',rooms_per_floor=6))

    def test_unsupported_shape_has_explicit_capability(self):
        b,_,_,_=self.fixture(); b.metadata['orientation_deg']=25
        self.assertFalse(interior_capability(b)['semantic_brief_supported'])

    def test_cache_signature_distinguishes_nearby_sizes_and_massing(self):
        b,_,_,_=self.fixture(); other=deepcopy(b)
        other.footprint=Bounds2D(0,0,40.5,14)
        self.assertNotEqual(BuildingFloorAgent.signature(b),BuildingFloorAgent.signature(other))
        other=deepcopy(b);other.metadata['massing_style']='l_shape'
        self.assertNotEqual(BuildingFloorAgent.signature(b),BuildingFloorAgent.signature(other))

    def test_nonfinite_weights_rejected(self):
        b,base,spec,brief=self.fixture(); brief['zones'][0]['spaces'][0]['weight']=float('nan')
        with self.assertRaises(ValueError): resolve_brief(brief,b,base,spec)

    def test_semantic_functions_cannot_disappear_to_obtain_a_fit(self):
        from dataclasses import replace
        b,base,spec,brief=self.fixture()
        base=replace(base,space_archetypes=tuple(replace(a,
            room_function_cycle=('living_room','kitchen','bathroom')) for a in base.space_archetypes))
        with self.assertRaisesRegex(ValueError,'omits accepted global functions'):
            resolve_brief(brief,b,base,spec)
        for zone in brief['zones']:
            zone['spaces'][0]['function']='kitchen'
            zone['spaces'][1]['function']='bathroom'
        resolve_brief(brief,b,base,spec)

    def test_agent_uses_direct_nested_schema_and_preserves_trace(self):
        import json
        b,base,spec,brief=self.fixture(); b.metadata['interior_layout_contract']={'reserved':True}
        from cityg.planning.floor_topologies import topology_catalog
        option=topology_catalog(geometry_summary(b,base))[0]
        brief={'zones':[{k:z[k] for k in ('zone_id','start_level','end_level','role','use_type')} | {
            'topology_id':option['id'],'functions':['living_room']*option['room_count'],
            'weight_adjustments':[1.0]*option['room_count']} for z in brief['zones']]}
        class Service:
            def complete(self, messages, response_schema=None):
                self.schema=response_schema
                return json.dumps(brief)
        service=Service()
        result=BuildingFloorAgent(service,model_id='test').plan(b,base,spec)
        self.assertIn('zones',service.schema['properties'])
        self.assertEqual(len(result.attempts),1)
        self.assertEqual(json.loads(json.loads(result.attempts[0].raw_output)['program_json']),brief)

    def test_independent_cell_width_is_constrained_before_allocation(self):
        from cityg.planning.spatial_layout import _place_band
        from cityg.planning.spatial_program import SpaceRequirement
        # The heavy room would previously get 18m frontage and fail afterward,
        # despite the feasible 14m/6m split under the closed-room aspect bound.
        spaces=[[SpaceRequirement('large','living_room',90)],
                [SpaceRequirement('small','living_room',10)]]
        boxes=_place_band(Bounds2D(0,0,20,5),spaces,True,2.4,2.8,12,0)
        self.assertAlmostEqual(boxes['large'].width,14)
        self.assertAlmostEqual(boxes['small'].width,6)

    def test_frozen_real_contracts_have_buildable_topology_choices(self):
        import json
        from pathlib import Path
        from cityg.serialization import _building
        from cityg.planning.floor_topologies import topology_catalog, expand_topology_brief
        from cityg.planning.floor_brief import required_functions_by_level
        rows=json.loads((Path(__file__).parent/'fixtures/floor_brief_contracts.json').read_text())['cases']
        self.assertEqual(len(rows),3)
        for row in rows:
            b=_building(row['building']); base=FloorProfile.from_dict(row['base_profile'])
            spec=CitySpec.from_dict(row['spec']); before=deepcopy(b)
            catalog=topology_catalog(geometry_summary(b,base))
            required=required_functions_by_level(b,base)
            self.assertTrue(catalog)
            # Check each organizational family, not only the easiest layout.
            choices={c['children_per_anchor']:c for c in catalog}
            for option in choices.values():
                zones=[]
                for floor in b.floors:
                    functions=required[str(floor.level)]
                    count=option['room_count']
                    zones.append({'zone_id':str(floor.level),'start_level':floor.level,
                        'end_level':floor.level,'role':'ground' if floor.level==0 else
                            'top' if floor.level==len(b.floors)-1 else 'typical',
                        'use_type':'residential' if b.function=='residential' else 'retail',
                        'topology_id':option['id'],
                        'functions':[functions[i%len(functions)] for i in range(count)],
                        'weight_adjustments':[1.0]*count})
                profile=resolve_brief(expand_topology_brief({'zones':zones},catalog),b,base,spec)
                BuildingFloorAgent._check_spatial_feasibility(profile,b,spec)
            self.assertEqual(before,b)

    def test_topology_personalization_is_bounded_and_exact_count(self):
        from cityg.planning.floor_topologies import topology_catalog, expand_topology_brief
        b,base,_,_=self.fixture(); catalog=topology_catalog(geometry_summary(b,base))
        c=catalog[0]; n=c['room_count']
        zone={'zone_id':'ground','start_level':0,'end_level':0,'role':'ground','use_type':'residential',
              'topology_id':c['id'],'functions':['living_room']*n,'weight_adjustments':[1.0]*n}
        zone['weight_adjustments'][0]=1.3
        with self.assertRaisesRegex(ValueError,'within'):
            expand_topology_brief({'zones':[zone]},catalog)
        zone['weight_adjustments'][0]=1.1
        expanded=expand_topology_brief({'zones':[zone]},catalog)
        self.assertAlmostEqual(expanded['zones'][0]['spaces'][0]['weight'],1.1*c['anchor_weight'])
        zone['functions'].pop()
        with self.assertRaisesRegex(ValueError,'exactly'):
            expand_topology_brief({'zones':[zone]},catalog)

    def test_required_slots_and_schema_cardinality_are_explicit(self):
        from cityg.planning.floor_topologies import topology_catalog,topology_schema,expand_topology_brief
        b,base,_,_=self.fixture();catalog=topology_catalog(geometry_summary(b,base))
        required={'0':['living_room','kitchen'],'1':['living_room','bedroom']}
        schema=topology_schema(['living_room','kitchen','bedroom'],['residential'],catalog,2,required)
        option=catalog[0]; n=option['room_count']
        for variant in schema['properties']['zones']['prefixItems'][0]['oneOf']:
            p=variant['properties']; count=p['weight_adjustments']['minItems']
            self.assertEqual(p['remaining_functions']['minItems'],count-2)
            self.assertEqual(p['remaining_functions']['minItems'],p['remaining_functions']['maxItems'])
        zone={'zone_id':'ground','start_level':0,'end_level':0,'role':'ground','use_type':'residential',
              'topology_id':option['id'],'required_function_slots':{'living_room':2,'kitchen':0},
              'remaining_functions':['bedroom']*(n-2),'weight_adjustments':[1.0]*n}
        spaces=expand_topology_brief({'zones':[zone]},catalog)['zones'][0]['spaces']
        self.assertEqual(spaces[0]['function'],'kitchen');self.assertEqual(spaces[2]['function'],'living_room')
        zone['required_function_slots']['living_room']=0
        with self.assertRaisesRegex(ValueError,'distinct'):
            expand_topology_brief({'zones':[zone]},catalog)

    def test_geometric_success_is_not_reference_compatibility(self):
        from cityg.planning.floor_reference_fit import check_floor_reference_fit
        from cityg.planning.floor_topologies import topology_catalog
        b,base,spec,brief=self.fixture()
        ref={'id':'living','function':'living_room','applicability':{
            'min_height_m':2.8,'width_m':[5.2,7],'depth_m':[5,6.5],
            'area_m2':[26,45],'aspect_ratio':[.85,1.4]}}
        geometry=geometry_summary(b,base)
        context={'room_dimensions':[ref],'minimum_compatible_rooms_per_detailed_floor':2,'detailed_levels':[0,1]}
        for z in brief['zones']: z['spaces']=z['spaces'][:6]
        profile=resolve_brief(brief,b,base,spec)
        BuildingFloorAgent._check_spatial_feasibility(profile,b,spec)
        with self.assertRaisesRegex(ValueError,'dimensionally match'):
            check_floor_reference_fit(profile,b,geometry,context)
        catalog=topology_catalog(geometry,references=[ref],allowed_functions=['living_room'])
        self.assertTrue(any(c['groups_per_side']==7 and c['children_per_anchor']==0 for c in catalog))
        for z in brief['zones']:
            z['spaces']=[{'key':f'living_{i}','function':'living_room','weight':1} for i in range(14)]
        profile=resolve_brief(brief,b,base,spec)
        reports=check_floor_reference_fit(profile,b,geometry,context)
        self.assertEqual([len(r['dimensionally_compatible_rooms']) for r in reports],[14,14])
