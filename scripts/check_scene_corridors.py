"""Check real slab support and continuous occupancy along indoor connections."""
import argparse
import hashlib
import json
from pathlib import Path

from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.transport import Box
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import inflated,hit_ids,supported_sweep,xy_bounds,rect_overlap,segment_bounds
from cityg.serialization import load_city,save_json


def check_connection(scene,building,floor,points,*,removed_source_ids=()):
    robot=Box('robot',points[0],(.65,.8,1.5));body=inflated(robot,.01)
    slabs=tuple(primitive_box(p) for p in scene.primitives if p.layer_id==f'shell:{building.id}'
        and p.collision_enabled and p.semantic_class=='collision_envelope' and p.size.z<.5
        and abs(p.center.z+p.size.z/2-floor.elevation_m)<1e-6)
    obstacles=[primitive_box(p) for p in scene.primitives if p.id not in removed_source_ids
        and (p.collision_enabled or p.semantic_class=='interior_wall' or p.metadata.get('surface_subentity'))
        and p.center.z+p.size.z/2>floor.elevation_m+1e-6
        and p.center.z-p.size.z/2<floor.elevation_m+2.0]
    segments=[]
    for start,end in zip(points,points[1:]):
        box=Box(body.id,start,body.size)
        local=[o for o in obstacles if rect_overlap(segment_bounds(box,end),xy_bounds(o))]
        hits=hit_ids(box,end,local);support=supported_sweep(box,end,slabs)
        payload=Box('held_cup',(start[0],start[1],start[2]+.825),(.09,.09,.11))
        payload_hits=hit_ids(payload,(end[0],end[1],end[2]+.825),local)
        segments.append({'start':start,'end':end,'supported':support,'robot_hits':hits,'payload_hits':payload_hits,
            'ok':support and not hits and not payload_hits})
    return {'ok':all(s['ok'] for s in segments),'segments':segments,'slab_count':len(slabs),
        'scope':'continuous_fixed_yaw_robot_payload_boxes_and_compiled_support'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Use a new report path')
    city=load_city(a.scene/'city.json');path=a.scene/'geometry_manifest.json'
    scene=scene_from_manifest(json.loads(path.read_text()));reports={}
    for bid,level in [('building_001',3),('building_000',6)]:
        b=next(b for b in city.iter_buildings() if b.id==bid);f=b.floors[level]
        main=next(r for r in f.rooms if r.id.endswith('_corridor'))
        door=next(d for d in f.doors if d.id.endswith('_space_g0_s0_door'))
        lift=next(c for c in b.vertical_connectors if c.connector_type=='elevator')
        x=lift.bounds.max_x+1.2;cy=lift.bounds.center.y;z=f.elevation_m+.75
        points=[(door.position.x-1.4,door.position.y+.025,z),(x,door.position.y+.025,z),(x,cy,z)]
        reports[bid+'_room_to_lift']=check_connection(scene,b,f,points)
        points=[(x,cy,.75),(main.bounds.center.x,cy,.75),(b.entrance.x,b.entrance.y-1.2,.75)]
        reports[bid+'_lift_to_entrance']=check_connection(scene,b,b.floors[0],points)
    result={'ok':all(r['ok'] for r in reports.values()),'connections':reports,
        'scene_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'model_calls':0,
        'exterior_route_checked':False,'full_city_task_verified':False}
    save_json(result,a.output);print(json.dumps(result,indent=2));return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
