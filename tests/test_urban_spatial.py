import unittest
from copy import deepcopy
from dataclasses import replace, asdict

from cityg.schemas import CitySpec, ZoneSpec, Bounds2D
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.building_site import adapt_building_site
from cityg.urban_requirements import evaluate, validate, UrbanPlanningConflict
from cityg.validation import CityValidator
from cityg.requirement_ledger import create_ledger, evaluate_ledger


class Empty:
    def populate(self, *args, **kwargs): return {}


def rule(subject='zone:homes',relation='north_half',target=None,threshold=None,strength='hard'):
    return {'id':subject+'_'+relation,'source_quote':'north homes; shops south; service within 120 m',
        'subject':subject,'relation':relation,'target':target,'threshold':threshold,
        'strength':strength,'reason':'explicit requested arrangement'}


def spec(**kwargs):
    return CitySpec(**{**dict(width_m=400,depth_m=360,building_count=12,min_floors=2,max_floors=3,
        rooms_per_floor=4,layout_style='regular_grid',road_pattern='connected_grid',
        zones=(ZoneSpec('homes','residential',.5),ZoneSpec('shops','commercial',.5))),**kwargs})


def make(s):return BaselineCityPlanner(floor_detail_agent=Empty()).plan(s)


def empty_rectangular_city():
    from cityg.ccwp import build_world_program
    c = make(spec(building_count=4))
    for b in c.iter_buildings():
        b.metadata['massing_style'] = 'bar'
    c.world_program = build_world_program(c, producer='rectangular_test_fixture', seed=17)
    return c


class UrbanSpatialTests(unittest.TestCase):
    def test_north_south_assignment_and_independent_acceptance(self):
        s=spec(urban_requirements=[rule(),rule('zone:shops','south_half')]);c=make(s)
        self.assertTrue(CityValidator().validate(c).ok)
        self.assertTrue(all(x['status']=='satisfied'for x in evaluate(c)))
        self.assertEqual(len([x for x in c.world_program.contracts if x.kind=='urban_spatial']),2)
        self.assertTrue(c.metadata['urban_spatial_assignment']['swaps'])
        old=deepcopy(c)
        b=next(b for b in c.iter_buildings() if b.function=='residential')
        b.footprint=Bounds2D(20,20,40,40)
        self.assertTrue(any(x.code=='urban_spatial_requirement' for x in CityValidator().validate(c).errors))
        ledger=evaluate_ledger(create_ledger('test',s),c)
        self.assertEqual(ledger['status'],'violated')
        self.assertNotEqual(evaluate(old),evaluate(c))

    def test_nearest_target_and_no_vacuous_success(self):
        c=make(spec())
        r=rule('function:residential','served_by','function:commercial',1000)
        self.assertEqual(evaluate(c,[r])[0]['status'],'satisfied')
        r['threshold']=1
        self.assertEqual(evaluate(c,[r])[0]['status'],'violated')
        r['target']='building:missing'
        self.assertEqual(evaluate(c,[r])[0]['status'],'violated')
        r['subject']='building:missing'
        self.assertEqual(evaluate(c,[r])[0]['status'],'violated')

    def test_schema_and_source(self):
        for bad in [rule(threshold=3),rule('zone:unknown'),rule(relation='near',target='river',threshold=30)]:
            with self.assertRaises(ValueError):validate([bad],spec=spec())
        with self.assertRaises(ValueError):validate([rule()],instruction='unrelated')
        with self.assertRaises(ValueError):validate([rule(),rule()])

    def test_soft_missing_relation_warns_without_hard_failure(self):
        s=spec(urban_requirements=[rule('function:residential','near','function:commercial',1,'soft')])
        c=make(s);v=CityValidator().validate(c)
        self.assertTrue(v.ok);self.assertTrue(v.warnings)
        self.assertNotEqual(evaluate_ledger(create_ledger('test',s),c)['status'],'violated')

    def test_capacity_before_children(self):
        base=spec(layout_style='organic_grid',layout_irregularity=1)
        c=make(base);b=next(c.iter_buildings());p=next(c.iter_parcels())
        area=(p.bounds.inset(base.parcel_setback_m).area+b.footprint.area)/2
        r=rule('building:'+b.id,'min_footprint_area',threshold=area)
        new=make(replace(base,urban_requirements=[r]));bb=next(new.iter_buildings())
        self.assertGreater(bb.footprint.area,b.footprint.area)
        self.assertTrue(CityValidator().validate(new).ok)
        self.assertTrue(all(bb.footprint.contains_bounds(room.bounds)for f in bb.floors for room in f.rooms))

    def test_impossible_capacity_reports_no_false_success(self):
        with self.assertRaises(UrbanPlanningConflict):
            make(spec(urban_requirements=[rule('function:residential','min_footprint_area',threshold=1e8)]))

    def test_waterfront_recovers_without_changing_user_geometry(self):
        s=spec(road_pattern='landscape_adaptive',parcel_layout='polygonal',river_mode='meandering',layout_style='organic_grid')
        c=make(s);self.assertEqual(c.metadata['geography_recovery']['status'],'recovered')
        self.assertEqual(len(list(c.iter_buildings())),12)
        self.assertEqual(c.rivers[0].width_m,s.river_width_m)
        self.assertEqual(c.rivers[0].setback_m,s.river_setback_m)
        self.assertTrue(CityValidator().validate(c).ok)

    def test_failed_geography_is_bounded(self):
        with self.assertRaises(UrbanPlanningConflict) as cm:
            make(spec(width_m=180,depth_m=180,road_pattern='landscape_adaptive',river_mode='meandering',parcel_layout='polygonal'))
        self.assertLessEqual(len(cm.exception.report['attempts']),3)

    def test_site_edit_atomic_geometry_and_compile(self):
        c=empty_rectangular_city();before=deepcopy(c);b=next(c.iter_buildings())
        result=adapt_building_site(c,b.id,{'area_m2':b.footprint.area*.8,'offset_y_m':1})
        new=next(result.city.iter_buildings())
        self.assertEqual(asdict(c),asdict(before))
        self.assertAlmostEqual(new.footprint.area,b.footprint.area*.8)
        self.assertEqual([f.height_m for f in new.floors],[f.height_m for f in b.floors])
        self.assertEqual([d.width_m for f in new.floors for d in f.doors],[d.width_m for f in b.floors for d in f.doors])
        self.assertEqual([asdict(x) for x in list(c.iter_buildings())[1:]],[asdict(x) for x in list(result.city.iter_buildings())[1:]])
        from cityg.geometry import GeometryCompiler,GeometryValidator
        scene=GeometryCompiler().compile(result.city)
        v=GeometryValidator().validate(result.city,scene)
        self.assertTrue(v.ok,v.to_dict())

    def test_site_rejects_locks_furnishing_and_outside(self):
        c=empty_rectangular_city();b=next(c.iter_buildings())
        with self.assertRaises(ValueError):adapt_building_site(c,b.id,{'offset_x_m':500})
        b.metadata['massing_style']='u_shape'
        with self.assertRaisesRegex(ValueError,'rectangular'):
            adapt_building_site(c,b.id,{'area_m2':b.footprint.area*.8})
        b.metadata['massing_style']='bar'
        b.floors[0].rooms[0].metadata['protected']=True
        with self.assertRaisesRegex(ValueError,'protected'):adapt_building_site(c,b.id,{'offset_x_m':1})
        b.floors[0].rooms[0].metadata.clear()
        next(n for n in c.world_program.nodes if n.entity_id==b.id).locked=True
        with self.assertRaisesRegex(ValueError,'locked'):adapt_building_site(c,b.id,{'offset_x_m':1})

    def test_furnished_resize_rebinds_actual_metric_pose_and_preserves_inventory(self):
        from cityg.ccwp import build_world_program
        from cityg.geometry import GeometryCompiler
        from cityg.planning.room_envelope import metric_envelope
        from cityg.planning.room_metric_frame import bind_metric_object, restore_metric_object
        from cityg.schemas import InteriorObject
        c=empty_rectangular_city()
        b=next(c.iter_buildings()); f=b.floors[0]
        room=next(r for r in f.rooms if r.function!='corridor')
        env=metric_envelope(b,f,room)
        desk=InteriorObject('test_desk',room.id,'desk','procedural::desk',
                            env['bounds'].center,1.2,.65,.75)
        bind_metric_object(desk,b,f,room,env)
        f.objects.append(desk); room.object_ids.append(desk.id)
        c.world_program=build_world_program(c,producer='test',seed=17)
        for req in ({'area_m2':b.footprint.area*.8},{'offset_y_m':0.5}):
            if 'offset_y_m' in req:
                c=after; b=target; env=updated
            after=adapt_building_site(c,b.id,req).city
            target=next(after.iter_buildings()); floor=target.floors[0]
            new_room=next(r for r in floor.rooms if r.id==room.id)
            updated=metric_envelope(target,floor,new_room)
            obj=restore_metric_object(floor.objects[0],target,floor,new_room,updated)
            self.assertEqual((obj.id,obj.asset_id,obj.width_m,obj.depth_m),
                             ('test_desk','procedural::desk',1.2,.65))
            if 'offset_y_m' in req:
                self.assertAlmostEqual(obj.position.y,env['bounds'].center.y+.5)
            scene=GeometryCompiler().compile(after,building_ids={b.id})
            self.assertTrue(any(p.owner_id==obj.id for p in scene.primitives))

    def test_exterior_only_tower_and_irregular_shell_edits(self):
        from cityg.geometry import GeometryCompiler, GeometryValidator
        for floors in (2,12):
            c=make(spec(building_count=4,min_floors=floors,max_floors=floors))
            b=next(c.iter_buildings())
            c.metadata['interior_scope']={'building_levels':{}}
            for request in ({'area_m2':b.footprint.area*.8}, {'aspect_ratio':b.footprint.width/b.footprint.depth*1.02,'area_m2':b.footprint.area*.9}):
                changed=adapt_building_site(c,b.id,request).city
                scene=GeometryCompiler(include_interiors=False).compile(changed)
                report=GeometryValidator().validate(changed,scene)
                self.assertTrue(report.ok,report.errors)
                moved=adapt_building_site(changed,b.id,{'offset_y_m':.5}).city
                self.assertAlmostEqual(next(moved.iter_buildings()).entrance.y,
                                       next(changed.iter_buildings()).entrance.y+.5)
            c.metadata.pop('interior_scope')
            with self.assertRaisesRegex(ValueError,'rectangular'):
                adapt_building_site(c,b.id,{'area_m2':b.footprint.area*.8})

    def test_programmed_empty_building_site_edit_compiles(self):
        from test_hierarchy_agents import HierarchyAgentTests
        from cityg.planning import HierarchicalProgram, ProgrammedCityPlanner
        from cityg.geometry import GeometryCompiler, GeometryValidator
        fixture = HierarchyAgentTests(); fixture.setUp()
        urban = fixture._urban(); skyline = fixture._skyline(urban)
        building = fixture._building(urban, skyline); floor = fixture._floor(building)
        from cityg.buildings.catalog import DEFAULT_BUILDING_CATALOG
        rectangular_id = next(a.archetype_id for a in DEFAULT_BUILDING_CATALOG
                              if a.massing_style=='bar' and 'residential' in a.compatible_functions)
        c = ProgrammedCityPlanner(HierarchicalProgram(urban,building,floor,skyline),
                                 floor_detail_agent=Empty(),
                                 archetype_pins={'building_000': rectangular_id}).plan(fixture.spec)
        b = next(c.iter_buildings())
        result = adapt_building_site(c,b.id,{'area_m2': b.footprint.area*.9})
        report = GeometryValidator().validate(result.city,GeometryCompiler().compile(result.city))
        self.assertTrue(report.ok,report.to_dict())

    def test_site_edit_cannot_break_spatial_contract(self):
        c=empty_rectangular_city();b=next(c.iter_buildings())
        c.metadata['urban_requirements']=[rule('building:'+b.id,'min_footprint_area',threshold=b.footprint.area*.95)]
        with self.assertRaises(ValueError):adapt_building_site(c,b.id,{'area_m2':b.footprint.area*.8})


if __name__=='__main__':unittest.main()
