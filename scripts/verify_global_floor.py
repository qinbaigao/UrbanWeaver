"""Replay a failed global Floor Agent against its frozen upstream programs."""
import argparse
from pathlib import Path
import json
from dataclasses import asdict

from cityg.agents.hierarchy import FloorAgent
from cityg.planning.generation_prototypes import GenerationPrototypes,load_options
from cityg.planning.programs import BuildingProgram
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.run_provenance import record_stage_start
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seed',type=int,default=101);args=p.parse_args()
    if args.output.exists(): p.error('Use a fresh output directory')
    spec=CitySpec.from_dict(json.loads((args.run/'requirement/requested_spec.json').read_text()))
    building=BuildingProgram.from_dict(json.loads((args.run/'programs/building_program.json').read_text()))
    selection=json.loads((args.run/'programs/prototype_selection.json').read_text())
    runtime=GenerationPrototypes(load_options('configs/reliability_prototypes.json'))
    record_stage_start(args.output)
    service=OpenAICompatibleService(ModelEndpoint('http://127.0.0.1:8000/v1','cityg-llm',
        timeout_s=180,max_tokens=6144,seed=args.seed))
    try:
        result=FloorAgent(service,max_calls=4).plan(spec,building,
            prototype_context=runtime.floor_context(selection))
        save_json(result.trace_dict(),args.output/'trace.json')
        report={'ok':True,'functions':[p.function for p in result.program.profiles],
                'calls':len(result.attempts),'full_pipeline_tested':False}
    except Exception as error:
        report={'ok':False,'error':str(error),'attempts':[asdict(a) for a in getattr(error,'attempts',())]}
    save_json(report,args.output/'report.json');print(report,flush=True)
    return 0 if report['ok'] else 3


if __name__=='__main__':raise SystemExit(main())
