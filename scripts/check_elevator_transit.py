"""Offline COMPILED SYNTHETIC elevator entry/ride/exit acceptance.

This probe exercises production geometry/runtime; it is explicitly not evidence
that the frozen paper city's missing elevators have been installed.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path

from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene,Vec3
from cityg.geometry.transport_elevator import compile_transport_elevator
from cityg.runtime.transport import Box
from cityg.runtime.elevator_transit import bind_elevator_transit,execute_elevator_transit,transit_task_from_dict
from cityg.runtime.elevator_validation import validate_elevator_transit
from cityg.schemas import Bounds2D,Floor,VerticalConnector
from cityg.serialization import save_json
from cityg.usd.writer import UsdaWriter


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    scene=GeometryScene('compiled_elevator_probe','right_handed_z_up_meters',
        metadata={'synthetic_probe':True,'actual_paper_city':False})
    compiler=GeometryCompiler()
    connector=VerticalConnector('probe_lift','elevator',Bounds2D(-1.2,-1.4,1.2,1.4),0,2,True,
        {'transport_elevator_version':1})
    floors={i:Floor(f'probe_floor_{i}',i,i*3.2,3.2) for i in range(3)}
    compile_transport_elevator(compiler,connector,floors,scene)
    slabs=tuple(Box(f'probe_landing_{i}',(0,-3.6,i*3.2-.1),(5,4,.2)) for i in range(3))
    for b in slabs:
        scene.primitives.append(compiler._box(b.id,b.id,Vec3(*b.center),Vec3(*b.size),b.yaw,
            'collision_envelope','industrial_metal','probe',metadata={'synthetic_landing':True}))
    manifest=save_json(scene,output/'geometry_manifest.json')
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    task=bind_elevator_transit(scene,scene_sha256=digest,elevator_id=connector.id,
        robot=Box('robot',(0,-2.4,.75),(.65,.8,1.5)),
        payload=Box('held_cup',(0,-2.4,1.575),(.09,.09,.11)),start_level=0,end_level=2,
        goal=(0,-2.4,7.15),obstacles=slabs,landing_slabs=slabs)
    save_json(asdict(task),output/'task.json')
    task=transit_task_from_dict(json.loads((output/'task.json').read_text()))
    trace=execute_elevator_transit(task);save_json(trace,output/'trace.json')
    checked=validate_elevator_transit(task,json.loads((output/'trace.json').read_text()))
    negatives={}
    for kind,expected in [('teleport','base_discontinuity'),('door','crossing_closed_lift_door'),
                          ('duplicate','object_identity_or_duplicate'),('open_while_moving','open_door_during_travel'),
                          ('stale','stale_transit_contract'),('missing_exit','incomplete_elevator_transit')]:
        bad=deepcopy(trace);f=next(f for f in bad['frames'] if f['action']=='enter')
        if kind=='teleport':f['robot_base'][1]+=.8
        elif kind=='door':f['opening']=0
        elif kind=='duplicate':f['objects']['copy']=deepcopy(f['objects'][task.payload.id])
        elif kind=='stale':f['contract_sha256']='stale'
        elif kind=='open_while_moving':next(f for f in bad['frames'] if f['action']=='ride')['opening']=1
        else:bad['frames']=[f for f in bad['frames'] if f['action'] not in ('exit','close_end','done')]
        result=validate_elevator_transit(task,bad)
        negatives[kind]={**result,'expected_error':expected,'expected_error_observed':expected in result['errors']}
    for kind,broken,expected in [
        ('missing_landing_support',replace(task,landing_slabs=()),'unsupported_entry_exit_sweep'),
        ('uncut_shaft_floor',replace(task,obstacles=(*task.obstacles,Box('uncut_floor',(0,0,3.1),(3,3,.2)))),
         'elevator_static_collision:uncut_floor')]:
        result=validate_elevator_transit(broken,execute_elevator_transit(broken))
        negatives[kind]={**result,'expected_error':expected,'expected_error_observed':expected in result['errors']}
    writer=UsdaWriter();lines=['#usda 1.0','(metersPerUnit = 1\n upAxis = "Z")']
    for p in scene.primitives:
        lines.extend(writer._kinematic_primitive(p,0) if p.body_type=='kinematic' else writer._static_collision(p,0))
    (output/'physics_geometry.usda').write_text('\n'.join(lines)+'\n')
    save_json(negatives,output/'negative_controls.json');save_json(checked,output/'independent_check.json')
    report={'ok':checked['ok'] and all(not r['ok'] and r['expected_error_observed'] for r in negatives.values()),
        'scope':'compiled_synthetic_elevator_entry_ride_exit','actual_paper_city':False,
        'kinematic_check':checked,'negative_controls':len(negatives),'geometry_sha256':digest,
        'all_elevator_parts_collision_enabled':all(p.collision_enabled for p in scene.primitives),
        'physics_dynamics_verified':False,'model_calls':0,'render_calls':0,
        'original_city_modified':False,'viewer_replay_implemented':False}
    save_json(report,output/'acceptance.json');return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=run(args.output);print(json.dumps(result,indent=2));return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
