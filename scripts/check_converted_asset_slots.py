#!/usr/bin/env python3
"""Exercise every accepted conversion through its runtime placement adapter."""
import argparse
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from cityg.assets import AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene, Vec3
from cityg.schemas import Point2D
from cityg.schemas import CitySpec
from cityg.planning import BaselineCityPlanner
from cityg.serialization import save_json
from cityg.viewer import export_portable_viewer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--export-viewer',type=Path,help='Diagnostic asset-only showcase, not a city generation result')
    args=parser.parse_args()
    registry=AssetRegistry('assets/asset_registry.json')
    rows=[]
    primitives=[]
    for record in registry.list_all():
        if not record.asset_id.startswith('converted_v3_') or record.metadata.get('outdoor_pack_status')!='ready':
            continue
        isolated=AssetRegistry()
        isolated.register(replace(record,geometry_path=str(registry.resolve_path(record.geometry_path).resolve())))
        compiler=GeometryCompiler(asset_registry=isolated,include_interiors=False)
        scene=GeometryScene(city_id='slot_test',coordinate_system='right_handed_z_up',materials=compiler._materials())
        street=compiler.streetscape_compiler
        road=SimpleNamespace(id='test_road')
        if record.category=='vehicle':
            kind=next(t for t in record.tags if t in {'sedan','suv','bus','pickup','ambulance','fire_truck'})
            resolved=street._vehicle(road,Point2D(10,10),23,0,scene,parked=False,vehicle_kind=kind)
        elif record.category=='person':
            resolved=street._pedestrian(road,Point2D(10,10),23,0,1,scene,state=record.metadata['static_pose'])
        else:
            envelope={'fountain':Vec3(3,3,2.8),'playground':Vec3(5.2,4.2,3.1),'bus_shelter':Vec3(3.4,1.45,2.55)}[record.category]
            primitive=compiler._outdoor_mesh('test_prop','slot_test',Vec3(10,10,envelope.z/2),envelope,
                                            23,record.category,record.category,' '.join(record.tags),'roads')
            resolved=primitive is not None
            if primitive:
                scene.primitives.append(primitive)
        assert resolved and len(scene.primitives)==1, record.asset_id
        primitive=scene.primitives[0]
        assert primitive.metadata['asset_id']==record.asset_id
        scales=[getattr(primitive.size,axis)/dimension for axis,dimension in zip('xyz',record.dimensions_m)]
        assert max(scales)-min(scales)<1e-8, 'Nonuniform stretch'
        assert abs(primitive.center.z-primitive.size.z/2)<1e-8, 'Floating/sunken base'
        if record.category=='person':
            assert 1.45<=primitive.size.z<=1.85, 'Implausible adult height'
        if record.category=='bus_shelter':
            rotations=[]
            for side in ('left','right'):
                probe=GeometryScene(city_id='side_test',coordinate_system='right_handed_z_up',materials=compiler._materials())
                assert street._asset('bus shelter','bus_shelter','road',Point2D(10,10),Vec3(3.4,1.45,2.55),
                                     23,'shelter',probe,semantic='bus_shelter',metadata={'side':side})
                rotations.append(probe.primitives[0].rotation_z_deg)
            assert (rotations[0]-rotations[1])%360==180, 'Shelter opening must face road from either side'
        rows.append({'asset_id':record.asset_id,'category':record.category,'ok':True,
                     'placed_dimensions_m':[primitive.size.x,primitive.size.y,primitive.size.z],
                     'rotation_z_deg':primitive.rotation_z_deg})
        primitives.append(primitive)
    assert rows, 'No promoted candidates'
    save_json({'ok':True,'checked_count':len(rows),'scope':'isolated_runtime_adapter_checks_not_city_placement',
               'checks':['exact_asset_binding','uniform_scale','ground_contact','adult_height'],'assets':rows},args.output)
    print(f'Passed {len(rows)} runtime slot checks: {args.output}')
    if args.export_viewer:
        if args.export_viewer.exists():
            raise ValueError('Diagnostic viewer output already exists')
        city=BaselineCityPlanner().plan(CitySpec(name='converted_asset_showcase',width_m=100,depth_m=90,
                                               building_count=1,min_floors=1,max_floors=1,rooms_per_floor=1))
        compiler=GeometryCompiler(include_interiors=False)
        scene=compiler.compile(city)
        ground=next(p for p in scene.primitives if p.semantic_class=='city_ground')
        scene.primitives=[ground]+[replace(p,id=f'showcase_{i}',owner_id=city.id,layer_id=ground.layer_id,
            center=Vec3(14+(i%5)*17,15+(i//5)*17,p.size.z/2),rotation_z_deg=0) for i,p in enumerate(primitives)]
        scene.metadata={'scope':'isolated_asset_showcase_not_city_generation','interiors_compiled':False}
        scene_path=args.export_viewer.parent/'asset_slot_scene'
        save_json(scene,scene_path/'geometry_manifest.json')
        save_json(city,scene_path/'city.json')
        used={row['asset_id'] for row in rows}
        save_json({'schema_version':'cityg.assets.v1','assets':[
            replace(r,geometry_path=str(registry.resolve_path(r.geometry_path).resolve())).to_dict()
            for r in registry.list_all() if r.asset_id in used]},scene_path/'assets/asset_registry.json')
        export_portable_viewer(scene_path,args.export_viewer)
        print(args.export_viewer)


if __name__=='__main__':
    main()
