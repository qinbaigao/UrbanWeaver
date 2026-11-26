"""Negative state controls on the actual version-bound Fetch trajectory."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path

from cityg.runtime.articulated_robot import RobotModel
from cityg.runtime.articulated_validation import validate_fetch_trace
from cityg.serialization import save_json
from check_fetch_transport import digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene',type=Path);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--robot',type=Path,default=Path('assets/robots/fetch/prepared'))
    args=parser.parse_args()
    task=json.loads((args.scene/'task/task.json').read_text())
    reference=json.loads((args.scene/'task/trace.json').read_text())
    trace=json.loads((args.run/'trace.json').read_text())
    report=json.loads((args.run/'acceptance.json').read_text())
    if (not report['ok'] or report['trace_sha256']!=digest(args.run/'trace.json')
        or report['robot_sha256']!=digest(args.robot/'robot.json')):raise ValueError('Unaccepted or stale input')
    model=RobotModel(json.loads((args.robot/'robot.json').read_text()))
    obj=task['object_id'];held=next(i for i,f in enumerate(trace['frames']) if f['action']=='stow_object')
    walking=next(i for i,f in enumerate(trace['frames']) if f['action']=='walk')
    door=next(i for i,f in enumerate(trace['frames']) if f['action']=='door' and any(f['doors'].values()))
    key=next(k for k,v in trace['frames'][door]['doors'].items() if v)
    def slip(t):
        f=t['frames'][walking];angle=math.radians(f['robot_yaw_deg'])
        for field in ('robot_root','robot_base'):
            f[field][0]-=.2*math.sin(angle);f[field][1]+=.2*math.cos(angle)
    cases=[
        ('joint_limit','joint_limit:torso_lift_joint',lambda t:t['frames'][held]['robot_joints'].update(torso_lift_joint=9)),
        ('wheel_odometry','wheel_odometry_mismatch',lambda t:t['frames'][walking]['robot_joints'].update(l_wheel_joint=0)),
        ('lost_attachment','attachment_state_sequence',lambda t:t['frames'][held]['objects'][obj].update(holder=None)),
        ('payload_teleport','attachment_position',lambda t:t['frames'][held]['objects'][obj]['position'].__setitem__(0,0)),
        ('lateral_slip','lateral_base_slip',slip),
        ('actuator_state','actuator_reference_mismatch',lambda t:t['frames'][door]['doors'].update({key:0})),
        ('nonfinite_payload','nonfinite_payload',lambda t:t['frames'][held]['objects'][obj]['position'].__setitem__(0,float('nan'))),
    ]
    results=[]
    for name,expected,mutate in cases:
        bad=deepcopy(trace);mutate(bad)
        checked=validate_fetch_trace(task,bad,model,None,reference=reference)
        results.append({'name':name,'rejected':not checked['ok'] and expected in checked['errors'],
                        'expected_error':expected,'errors':checked['errors']})
        print(name,results[-1]['rejected'],flush=True)
    result={'ok':all(c['rejected'] for c in results),'trace_sha256':report['trace_sha256'],'cases':results}
    save_json(result,args.run/'negative_controls.json')
    return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
