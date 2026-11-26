"""Construct geometric feasibility certificates, independently of all three planning arms."""
from copy import deepcopy
import json
from pathlib import Path

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.schemas import Point2D, Bounds2D, InteriorObject
from cityg.serialization import load_city
from cityg.validation import CityValidator
from score import check, point, rect, overlaps, EPS

ROOT=Path(__file__).resolve().parents[1]


def xy(u,v,axis):
    return Point2D(u,v) if axis=='x' else Point2D(v,u)


def box_uv(u,v,h,j,axis):
    a=xy(u,v,axis);b=xy(h,j,axis)
    return Bounds2D(a.x,a.y,b.x,b.y)


def certify_site(city,task):
    q=task['request'];ax=q['span_axis']; p=next(p for p in city.iter_parcels() if p.id==q['parcel'])
    b=next(b for b in p.buildings if b.id==q['target'])
    a,v,h,j=rect(b.footprint,ax)
    c,z=(a+h)/2,(v+j)/2; half=q['min_span_m']/2; depth=q['min_depth_m']/2
    lo,bottom,hi,top=rect(p.bounds.inset(q['setback_m']),ax)
    obstacles=[rect(Bounds2D(**v),ax) for v in q['keepout_boxes']]
    obstacles.extend(rect(o.footprint,ax) for o in city.iter_buildings() if o.id!=b.id)
    cuts={lo+half,hi-half}
    for u,w,s,t in obstacles:
        cuts.update([u-half,s+half])
    ends=sorted(cuts)
    # Open obstacle interiors; endpoint contact can be feasible independently of either adjacent interval.
    probes=[c,*ends,*[(x+y)/2 for x,y in zip(ends,ends[1:])]]
    for u in probes:
        if not (lo+half<=u+EPS and u<=hi-half+EPS and bottom+depth<=z+EPS and z<=top-depth+EPS):
            continue
        rectangle=(u-half,z-depth,u+half,z+depth)
        if any(overlaps(rectangle,o) for o in obstacles): continue
        edited=deepcopy(city);dst=next(t for t in edited.iter_buildings() if t.id==b.id)
        def move(p):
            x,y=point(p,ax)
            return xy(u-half+(x-a)*2*half/(h-a),z-depth+(y-v)*2*depth/(j-v),ax)
        def resize(r):
            x=move(Point2D(r.min_x,r.min_y));y=move(Point2D(r.max_x,r.max_y))
            return Bounds2D(x.x,x.y,y.x,y.y)
        dst.footprint=resize(dst.footprint);dst.entrance=move(dst.entrance)
        for f in dst.floors:
            for room in f.rooms: room.bounds=resize(room.bounds)
            for door in f.doors: door.position=move(door.position)
        return ('local' if abs(u-c)<=EPS else 'cross_scale',edited,
                {'initial_center':c,'witness_center':u,'min_span':half*2})
    return 'infeasible',None,{'center_interval':[lo+half,hi-half],'obstacle_intervals':[
        [x-half,y+half] for x,t,y,w in obstacles if w>z-depth and t<z+depth],
        'required_depth_interval':[z-depth,z+depth],'usable_depth_interval':[bottom,top]}


def certify_interior(city,task):
    q=task['request'];ax=q['span_axis']
    edited=deepcopy(city);b=next(b for b in edited.iter_buildings() if b.id==q['target']);f=b.floors[0]
    r=next(r for r in f.rooms if r.id==q['room']); donor=next(r for r in f.rooms if r.id==q['donor'])
    l,v,h,j=rect(r.bounds,ax); dl,dv,dh,dj=rect(donor.bounds,ax)
    left=l<dl
    door=next(d for d in f.doors if donor.id in (d.room_a_id,d.room_b_id))
    u,_=point(door.position,ax);half=door.width_m/2+q['door_jamb_m']
    min_donor=max(q['min_donor_span_m'],(dh-u if left else u-dl)+half)
    max_receiver=h-l+dh-dl-min_donor
    parts=q['kit'];gap=q['wall_gap_m']
    min_u=min(p['offset_uv_m'][0]-p['size_uvh_m'][0]/2 for p in parts)
    max_u=max(p['offset_uv_m'][0]+p['size_uvh_m'][0]/2 for p in parts)
    need=max_u-min_u+2*gap
    certificate={'minimum_kit_span_with_gap':round(need,6),'original_span':round(h-l,6),
                 'max_receiver_span_with_door_and_donor':round(max_receiver,6)}
    if max_receiver+EPS<need: return 'infeasible',None,certificate
    delta=max(0.,need-(h-l))
    if left: h+=delta;dl+=delta
    else: l-=delta;dh-=delta
    r.bounds=box_uv(l,v,h,j,ax);donor.bounds=box_uv(dl,dv,dh,dj,ax)
    max_v=max(p['offset_uv_m'][1]+p['size_uvh_m'][1]/2 for p in parts)
    for p in parts:
        u0,v0=p['offset_uv_m']; width,depth,height=p['size_uvh_m']
        pos=xy(l+(h-l-need)/2+gap-min_u+u0,j-gap-max_v+v0,ax)
        obj=InteriorObject(p['id'],r.id,p['category'],'procedural::'+p['category'],pos,width,depth,height,
                           rotation_deg=0 if ax=='x' else 90)
        r.object_ids.append(obj.id);f.objects.append(obj)
    return ('local' if delta<=EPS else 'cross_scale'),edited,certificate


def main():
    report={};seen=set()
    for split in ('development','test'):
        data=ROOT/split
        tasks=[json.loads(l) for l in (data/'tasks.jsonl').read_text().splitlines()]
        gold={r['id']:r for r in map(json.loads,(ROOT/'evaluation'/f'{split}_labels.jsonl').read_text().splitlines())}
        assert len(tasks)==len(gold) and {t['id'] for t in tasks}==gold.keys()
        rows=[]
        for t in tasks:
            assert t['id'] not in seen
            seen.add(t['id']);src=load_city(data/t['scene'])
            assert CityValidator().validate(src).ok
            assert GeometryValidator().validate(src,GeometryCompiler().compile(src)).ok
            assert not all(check(t,src,src,compile_geometry=False).values()),t['id']
            classify=certify_site if t['request']['kind']=='site' else certify_interior
            label, witness, proof=classify(src,t)
            assert label==gold[t['id']]['expected'],(t['id'],label,proof)
            if witness is not None:
                witness.world_program=build_world_program(witness,producer='independent_certificate',seed=11)
                gates=check(t,src,witness)
                assert all(gates.values()),(t['id'],gates)
                local=check(t,src,witness,compile_geometry=False,local_only=True)
                assert all(local.values())==(label=='local'),(t['id'],local)
            rows.append(dict(id=t['id'],family=gold[t['id']]['family'],expected=label,
                             certificate=proof,compiled_witness=witness is not None))
        report[split]=rows

    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
