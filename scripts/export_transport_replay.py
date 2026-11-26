"""Package an accepted version-bound task and its final persistent overlay."""
import argparse
import hashlib
import json
from pathlib import Path

from cityg.runtime.city_transport import contract_hash
from cityg.serialization import save_json
from cityg.viewer import export_portable_viewer


def prepare_replay(scene_dir,task_dir):
    task=json.loads((task_dir/'task.json').read_text());trace=json.loads((task_dir/'trace.json').read_text())
    checked=json.loads((task_dir/'independent_check.json').read_text())
    digest=hashlib.sha256((scene_dir/'geometry_manifest.json').read_bytes()).hexdigest()
    if (not checked['ok'] or digest!=checked['scene_sha256'] or task['scene_sha256']!=digest
        or checked['contract_sha256']!=contract_hash(task)
        or checked['trace_sha256']!=hashlib.sha256((task_dir/'trace.json').read_bytes()).hexdigest()):
        raise ValueError('Refusing stale or unaccepted replay')
    save_json({'schema_version':'cityg.task_replay.v1','scene_sha256':digest,
               'acceptance':checked,'task':task,'trace':trace},scene_dir/'task_replay.json')
    save_json({'schema_version':'cityg.task_state_overlay.v1','scene_sha256':digest,
        'contract_sha256':checked['contract_sha256'],'suppress_primitive_ids':task['source_primitive_ids'],
        'final_state':trace['frames'][-1],'canonical_city_rewritten':False,
        'meaning':'Simulation state overlay; apply instead of duplicating the original cup.'},scene_dir/'final_state_overlay.json')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path)
    p.add_argument('--task',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    prepare_replay(a.scene,a.task)
    print(export_portable_viewer(a.scene,a.output))


if __name__=='__main__':main()
