"""Prune completed repair diagnostics only, preserving compact audit evidence."""
import argparse
import gzip
from pathlib import Path
import shutil

from cityg.serialization import save_json
from run_analysis44 import compress_and_prune, read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();root=args.root.resolve()
    project=Path(__file__).resolve().parents[1]
    if root.parent!=project/'analysis_results' or not root.name.startswith('analysis44_repairs_'):
        parser.error('Only an explicit analysis_results/analysis44_repairs_* suite may be cleaned')
    summary=read(root/'summary.json',{})
    if summary.get('completed')!=len(summary.get('protocol',{}).get('cases',[])) or not summary.get('completed'):
        parser.error('Generation suite must be complete')
    if not (root/'repair_diagnostics.json').is_file() or not (root/'visual_review/branch_summary.json').is_file():
        parser.error('Audit and visual branch must finish first')
    folders=[root/'runs'/r['id'] for r in summary['rows']]
    for folder in folders:
        if folder.resolve().parent!=root/'runs' or folder.is_symlink():
            parser.error('Unexpected case target')
    drops=[root/'visual_review'/n for n in ('openusd_after','viewer_after','runtime_assets')]
    def size():return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    before=size()
    print({'suite':str(root),'bytes_before':before,'completed_cases':len(folders),
           'review_directories':[str(p) for p in drops if p.exists()],'apply':args.apply},flush=True)
    if not args.apply:return
    for folder in folders:compress_and_prune(folder,keep_scene=False)
    compiled=root/'visual_review/openusd_after'
    if compiled.exists():
        evidence=root/'visual_review/compiled_evidence';evidence.mkdir(exist_ok=True)
        for path in compiled.glob('*.json'):
            with path.open('rb') as source,gzip.open(evidence/(path.name+'.gz'),'wb') as target:
                shutil.copyfileobj(source,target)
    removed=[]
    for path in drops:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path);removed.append(str(path.relative_to(root)))
    for path in root.rglob('*.json'):
        if path.stat().st_size>100_000 and path.name not in {'repair_diagnostics.json','summary.json'}:
            with path.open('rb') as source,gzip.open(str(path)+'.gz','wb') as target:
                shutil.copyfileobj(source,target)
            path.unlink()
    save_json({'bytes_before':before,'bytes_after':size(),'removed_review_directories':removed,
        'completed_case_binaries_pruned':True,'screenshots_and_traces_preserved':True,
        'recovery':'Canonical cities and JSON/log traces retained; rebuild USD and Viewer from canonical scenes and assets.'},root/'cleanup.json')


if __name__=='__main__':main()
