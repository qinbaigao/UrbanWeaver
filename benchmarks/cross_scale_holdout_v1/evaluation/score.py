"""Score a delivered native city against the public brief; no access to a planning trace."""
import argparse
import json
import math
from pathlib import Path

from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.serialization import load_city
from cityg.validation import CityValidator

EPS=1e-5


def point(p, axis):
    return (p.x,p.y) if axis=='x' else (p.y,p.x)


def rect(b,axis):
    if axis=='x':
        return (b.min_x,b.min_y,b.max_x,b.max_y)
    return (b.min_y,b.min_x,b.max_y,b.max_x)


def close(a,b):
    return len(a)==len(b) and all(math.isclose(x,y,rel_tol=0,abs_tol=EPS) for x,y in zip(a,b))


def overlaps(a,b):
    return min(a[2],b[2])-max(a[0],b[0])>EPS and min(a[3],b[3])-max(a[1],b[1])>EPS


def in_box(small,big):
    return (big[0]-EPS<=small[0]<=small[2]<=big[2]+EPS and
            big[1]-EPS<=small[1]<=small[3]<=big[3]+EPS)


def check(task, base, final, *, compile_geometry=True, local_only=False):
    from cityg.schemas import Bounds2D
    from cityg.envelopes import envelope_config
    q=task['request']; ax=q['span_axis']
    buildings={b.id:b for b in final.iter_buildings()}
    original={b.id:b for b in base.iter_buildings()}
    bid=q['target']
    fixed_city=(final.id==base.id and final.bounds==base.bounds and final.road_network==base.road_network
                and final.rivers==base.rivers and final.bridges==base.bridges
                and [(d.id,d.name,d.function,d.bounds,[(p.id,p.bounds,p.boundary,p.holes,[b.id for b in p.buildings])
                       for p in d.parcels]) for d in base.districts]
                == [(d.id,d.name,d.function,d.bounds,[(p.id,p.bounds,p.boundary,p.holes,[b.id for b in p.buildings])
                       for p in d.parcels]) for d in final.districts]
                and buildings.keys()==original.keys()
                and all(b==buildings[k] for k,b in original.items() if k!=bid))
    gates={'city_and_neighbors_preserved':fixed_city}
    if bid not in buildings: return gates
    b=buildings[bid]; old=original[bid]; floor=b.floors[0] if len(b.floors)==1 else None
    gates['shell_identity']=(b.function==old.function and b.name==old.name and floor is not None and
                            floor.id==old.floors[0].id and floor.height_m==old.floors[0].height_m
                            and floor.level==0 and floor.elevation_m==old.floors[0].elevation_m
                            and b.vertical_connectors==old.vertical_connectors)
    if floor is None: return gates
    geo=rect(b.footprint,ax)
    initial=rect(old.footprint,ax)
    if q['kind']=='site':
        if local_only:
            gates['local_scope']=close(point(old.footprint.center,ax),point(b.footprint.center,ax))
        parcel=next(p for p in base.iter_parcels() if p.id==q['parcel'])
        obstacles=[rect(Bounds2D(**v),ax) for v in q['keepout_boxes']]
        obstacles.extend(rect(n.footprint,ax) for n in original.values() if n.id!=bid)
        gates['site_limits']=(in_box(geo,rect(parcel.bounds.inset(q['setback_m']),ax))
                              and not any(overlaps(geo,obs) for obs in obstacles))
        gates['frontage_depth']=(geo[2]-geo[0]+EPS>=q['min_span_m'] and geo[3]-geo[1]+EPS>=q['min_depth_m'])
        # Site adapters add audit metadata. Geometry-changing shell policies are outside this fixture.
        gates['rectangular_shell']=not envelope_config(b) and not b.metadata.get('massing_style')
        gates['street_alignment']=(abs((geo[1]+geo[3])-(initial[1]+initial[3]))<=EPS
                                   and abs(point(b.entrance,ax)[1]-geo[1])<=EPS
                                   and abs(b.metadata.get('orientation_deg',0)%360)<=EPS)
        gates['original_spaces']=({(r.id,r.function) for r in floor.rooms}==
                                  {(r.id,r.function) for r in old.floors[0].rooms} and
                                  {(d.id,d.room_a_id,d.room_b_id) for d in floor.doors}==
                                  {(d.id,d.room_a_id,d.room_b_id) for d in old.floors[0].doors}
                                  and floor.objects==old.floors[0].objects)
    else:
        gates['shell_and_doors_fixed']=(geo==initial and b.entrance==old.entrance and
            floor.doors==old.floors[0].doors and not envelope_config(b) and not b.metadata.get('massing_style')
            and not b.metadata.get('orientation_deg'))
        rooms={r.id:r for r in floor.rooms}; before={r.id:r for r in old.floors[0].rooms}
        rid,did=q['room'],q['donor']
        if not {rid,did}<=rooms.keys(): return {**gates,'rooms_present':False}
        rg,dg=rect(rooms[rid].bounds,ax),rect(rooms[did].bounds,ax)
        r0,d0=rect(before[rid].bounds,ax),rect(before[did].bounds,ax)
        if local_only:
            gates['local_scope']=close(rg,r0) and close(dg,d0)
        left=r0[0]<d0[0]
        fixed_partition_geometry=(close((rg[1],rg[3],dg[1],dg[3]),(r0[1],r0[3],d0[1],d0[3])) and
            (close((rg[0],rg[2],dg[2]),(r0[0],dg[0],d0[2])) if left else
             close((dg[0],dg[2],rg[2]),(d0[0],rg[0],r0[2]))))
        gates['shared_partition_only']=(rooms.keys()==before.keys() and fixed_partition_geometry and
            all((r.name,r.function,r.height_m)==(before[k].name,before[k].function,before[k].height_m)
                for k,r in rooms.items()) and all(r==before[k] for k,r in rooms.items() if k not in (rid,did)))
        gates['donor_width']=dg[2]-dg[0]+EPS>=q['min_donor_span_m']
        forbidden=[]
        jambs=[]
        for door in old.floors[0].doors:
            u,v=point(door.position,ax); half=door.width_m/2+q['door_jamb_m']
            for room_id, rr in ((rid,rg),(did,dg)):
                if room_id not in (door.room_a_id,door.room_b_id): continue
                jambs.append(rr[0]-EPS<=u-half and u+half<=rr[2]+EPS)
                if room_id==rid: forbidden.append((u-half,v,u+half,v+q['door_keep_clear_depth_m']))
        gates['door_jambs']=bool(jambs) and all(jambs)
        actual={o.id:o for o in floor.objects}
        gates['kit_inventory']=(len(actual)==len(floor.objects)==len(q['kit'])
            and set(actual)=={p['id'] for p in q['kit']} and set(rooms[rid].object_ids)==set(actual))
        if gates['kit_inventory']:
            poses=[];bounds=[];parts=[]
            gap=q['wall_gap_m']
            for part in q['kit']:
                obj=actual[part['id']];u,v=point(obj.position,ax);du,dv=part['offset_uv_m']
                poses.append((u-du,v-dv))
                parts.append(obj.room_id==rid and obj.category==part['category'] and
                             close((obj.width_m,obj.depth_m,obj.height_m),part['size_uvh_m'])
                             and abs((obj.rotation_deg-(0 if ax=='x' else 90)+180)%360-180)<=EPS)
                bounds.append(rect(obj.bounds,ax))
            gates['kit_configuration']=all(parts) and all(close(pos,poses[0]) for pos in poses)
            gates['wall_and_door_clearance']=all(in_box(bb,(rg[0]+gap,rg[1]+gap,rg[2]-gap,rg[3]-gap))
                and not any(overlaps(bb,zone) for zone in forbidden+bounds[:i]) for i,bb in enumerate(bounds))
    gates['canonical']=CityValidator().validate(final).ok
    if compile_geometry and gates['canonical']:
        scene=GeometryCompiler().compile(final)
        gates['compiled']=GeometryValidator().validate(final,scene).ok
        owners={p.owner_id for p in scene.primitives}
        gates['realized_doors']=all(d.id in owners for d in floor.doors)
        if q['kind']=='interior':
            gates['realized_kit']=all(p['id'] in owners for p in q['kit'])
    return gates


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('task_id')
    p.add_argument('final_city',type=Path);p.add_argument('--split',choices=['development','test'],default='development')
    p.add_argument('--local-only',action='store_true',help='Enforce the leaf arm on the delivered geometry')
    args=p.parse_args(); data=Path(__file__).resolve().parents[1]/args.split
    rows=[json.loads(l) for l in (data/'tasks.jsonl').read_text().splitlines()]
    task=next(t for t in rows if t['id']==args.task_id)
    gates=check(task,load_city(data/task['scene']),load_city(args.final_city),local_only=args.local_only)
    print(json.dumps({'delivery_pass':all(gates.values()),'checks':gates},ensure_ascii=False,indent=2))
    return 0 if all(gates.values()) else 1


if __name__=='__main__':raise SystemExit(main())
