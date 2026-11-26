"""Export a hash-bound accepted Fetch replay without modifying its source city."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from cityg.runtime.city_transport import contract_hash
from cityg.serialization import save_json
from cityg.viewer import export_portable_viewer


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def export(scene,run,robot,output):
    report=json.loads((run/'acceptance.json').read_text())
    task=json.loads((scene/'task/task.json').read_text())
    trace=json.loads((run/'trace.json').read_text())
    spec=json.loads((robot/'robot.json').read_text())
    if (not report['ok'] or report.get('stride')!=1 or report['scene_sha256']!=digest(scene/'geometry_manifest.json')
        or report['trace_sha256']!=digest(run/'trace.json') or report['robot_sha256']!=digest(robot/'robot.json')
        or report['source_contract_sha256']!=contract_hash(task) or spec['glb_sha256']!=digest(robot/'fetch.glb')):
        raise ValueError('Refusing stale, diagnostic-only or unaccepted Fetch replay')
    export_portable_viewer(scene,output)
    bundle={'schema_version':'cityg.task_replay.v2','scene_sha256':report['scene_sha256'],
            'acceptance':report,'task':task,'trace':trace,'robot_model':spec}
    save_json(bundle,output/'scene/task_replay.json')
    shutil.copy2(robot/'fetch.glb',output/'scene/robot_model.glb')
    config=json.loads((output/'viewer-config.json').read_text())
    config['files']=sorted(set(config['files'])|{'robot_model.glb','task_replay.json'})
    save_json(config,output/'viewer-config.json')
    notice=('Fetch robot model: Fetch Robotics\nSource: '+spec['source_url']+'\nRevision: '+spec['revision']+
            '\nDeclared model license: '+spec['license_declaration']+
            '\nhttps://creativecommons.org/licenses/by-nc-sa/4.0/\n'+
            'Changes: DAE/STL to GLB conversion; original scale, materials and link frames retained.\n'+
            'CityG code license does not relicense this third-party robot asset.\n\n'+(robot/'package.xml').read_text())
    (output/'FETCH_MODEL_NOTICE.txt').write_text(notice)
    save_json({'schema_version':'cityg.task_state_overlay.v2','scene_sha256':report['scene_sha256'],
               'trace_sha256':report['trace_sha256'],'suppress_primitive_ids':task['source_primitive_ids'],
               'final_state':trace['frames'][-1],'canonical_city_rewritten':False},run/'final_state_overlay.json')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene',type=Path)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--robot',type=Path,default=Path('assets/robots/fetch/prepared'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(export(args.scene,args.run,args.robot,args.output))


if __name__=='__main__':main()
