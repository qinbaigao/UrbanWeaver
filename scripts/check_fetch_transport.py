"""Build and independently check a Fetch adaptation of an accepted city route."""
import argparse
import hashlib
import json
from pathlib import Path

from cityg.geometry.incremental import scene_from_manifest
from cityg.runtime.articulated_robot import RobotModel
from cityg.runtime.articulated_validation import validate_fetch_trace
from cityg.runtime.city_transport import contract_hash
from cityg.runtime.fetch_transport import adapt_fetch_trace
from cityg.runtime.fetch_pose_gate import FetchPoseGate
from cityg.serialization import save_json


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene',type=Path)
    parser.add_argument('--robot',type=Path,default=Path('assets/robots/fetch/prepared'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse-trace',action='store_true')
    parser.add_argument('--replan',action='store_true',help='Replace this adapter output only, never the source task')
    parser.add_argument('--stride',type=int,default=1,help='>1 is diagnostic only, never an acceptance')
    parser.add_argument('--max-collision-frames',type=int,help='Bounded diagnostic, never an acceptance')
    parser.add_argument('--start-collision-frame',type=int,default=0)
    args=parser.parse_args()
    if args.output.resolve()==args.scene.resolve() or args.scene.resolve() in args.output.resolve().parents:
        raise ValueError('Keep Fetch adaptation outside the frozen source package')
    if args.stride<1:raise ValueError('Positive stride required')
    if args.start_collision_frame<0 or (args.max_collision_frames is not None and args.max_collision_frames<1):
        raise ValueError('Nonnegative start and positive diagnostic frame count required')
    task=json.loads((args.scene/'task/task.json').read_text())
    trace=json.loads((args.scene/'task/trace.json').read_text())
    checked=json.loads((args.scene/'task/independent_check.json').read_text())
    geometry=args.scene/'geometry_manifest.json'
    if (not checked['ok'] or checked['scene_sha256']!=digest(geometry)
        or checked['trace_sha256']!=digest(args.scene/'task/trace.json')
        or checked['contract_sha256']!=contract_hash(task)):
        raise ValueError('Input proxy task must be accepted and version-bound')
    spec_path=args.robot/'robot.json';spec=json.loads(spec_path.read_text())
    if spec['glb_sha256']!=digest(args.robot/'fetch.glb'):raise ValueError('Stale robot asset')
    model=RobotModel(spec)
    scene=scene_from_manifest(json.loads(geometry.read_text()))
    bindings={'scene_sha256':digest(geometry),'robot_sha256':digest(spec_path),
              'source_contract_sha256':contract_hash(task)}
    args.output.mkdir(parents=True,exist_ok=True)
    if args.reuse_trace:
        candidate=json.loads((args.output/'trace.json').read_text())
    else:
        if (args.output/'trace.json').exists() and not args.replan:raise ValueError('Use --reuse-trace, --replan or a new output directory')
        candidate=adapt_fetch_trace(task,trace,model,pose_gate=FetchPoseGate(scene,task,model))
        candidate.update(scene_sha256=digest(geometry),source_contract_sha256=contract_hash(task),
                         source_trace_sha256=digest(args.scene/'task/trace.json'),robot_sha256=digest(spec_path))
        save_json(candidate,args.output/'trace.json')
    if (candidate.get('robot_sha256')!=digest(spec_path) or candidate.get('source_trace_sha256')!=digest(args.scene/'task/trace.json')
        or candidate.get('scene_sha256')!=digest(geometry)):
        raise ValueError('Stale adapted trace')
    report=validate_fetch_trace(task,candidate,model,scene,stride=args.stride,reference=trace,max_collision_frames=args.max_collision_frames,start_collision_frame=args.start_collision_frame)
    trace_digest=digest(args.output/'trace.json')
    # Reject a concurrent edit instead of binding a checked in-memory trace to
    # a newer on-disk file that was never checked.
    if (json.loads((args.output/'trace.json').read_text())!=candidate
        or bindings['robot_sha256']!=digest(spec_path) or bindings['scene_sha256']!=digest(geometry)):
        raise ValueError('Inputs changed during audit; rerun against a stable snapshot')
    report.update(**bindings,trace_sha256=trace_digest)
    save_json(report,args.output/('acceptance.json' if args.stride==1 and args.max_collision_frames is None and args.start_collision_frame==0 else 'diagnostic.json'))
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report.get('diagnostic_ok',report['ok']) else 2


if __name__=='__main__':raise SystemExit(main())
