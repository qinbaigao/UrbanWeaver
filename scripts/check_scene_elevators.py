"""Bind entry/ride/exit to a compiled city, never a synthetic substitute."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.transport import Box
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import rect_overlap,xy_bounds,hit_ids,inflated,supported_sweep
from cityg.runtime.elevator_transit import bind_elevator_transit,execute_elevator_transit,transit_task_from_dict
from cityg.runtime.elevator_validation import validate_elevator_transit
from cityg.serialization import load_city,save_json


def bind_scene_elevator(city,scene,digest,building_id,start_level,end_level):
    b=next(b for b in city.iter_buildings() if b.id==building_id)
    c=next(c for c in b.vertical_connectors if c.metadata.get('transport_elevator_version')==1)
    if c.metadata['entrance_rotation_deg']!=90:raise ValueError('This fixture adapter expects east entrance')
    levels={f.level:f for f in b.floors}
    x=c.bounds.max_x+1.2;y=c.bounds.center.y
    z0=levels[start_level].elevation_m;z1=levels[end_level].elevation_m
    envelope=(c.bounds.min_x-1,c.bounds.min_y-1,c.bounds.max_x+2,c.bounds.max_y+1)
    obstacles=[];slabs=[]
    for p in scene.primitives:
        if p.owner_id==c.id or not (p.collision_enabled or p.semantic_class=='interior_wall' or p.metadata.get('surface_subentity')):continue
        if p.center.z+p.size.z/2<min(z0,z1)-.5 or p.center.z-p.size.z/2>max(z0,z1)+3:continue
        box=primitive_box(p)
        if not rect_overlap(xy_bounds(box),envelope):continue
        obstacles.append(box)
        if p.layer_id==f'shell:{b.id}' and p.semantic_class=='collision_envelope' and p.size.z<.5:
            slabs.append(box)
    return bind_elevator_transit(scene,scene_sha256=digest,elevator_id=c.id,
        robot=Box('scripted_robot_base',(x,y,z0+.75),(.65,.8,1.5)),
        payload=Box('held_cup',(x,y,z0+1.575),(.09,.09,.11)),
        start_level=start_level,end_level=end_level,goal=(x,y,z1+.75),
        obstacles=tuple(obstacles),landing_slabs=tuple(slabs))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('scene',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a new output directory')
    city=load_city(args.scene/'city.json');path=args.scene/'geometry_manifest.json'
    scene=scene_from_manifest(json.loads(path.read_text()));digest=hashlib.sha256(path.read_bytes()).hexdigest()
    args.output.mkdir(parents=True);reports={}
    for building,start,end in [('building_001',3,0),('building_000',0,6)]:
        task=bind_scene_elevator(city,scene,digest,building,start,end)
        root=args.output/building;save_json(asdict(task),root/'task.json')
        task=transit_task_from_dict(json.loads((root/'task.json').read_text()))
        trace=execute_elevator_transit(task);save_json(trace,root/'trace.json')
        checked=validate_elevator_transit(task,trace);save_json(checked,root/'independent_check.json')
        reports[building]=checked
        print(building,json.dumps(checked),flush=True)
    result={'ok':all(r['ok'] for r in reports.values()),'actual_city_geometry':True,
        'scene_sha256':digest,'source':str(args.scene.resolve()),'elevators':reports,
        'model_calls':0,'full_city_route_verified':False,'physics_dynamics_verified':False}
    save_json(result,args.output/'acceptance.json')
    return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
