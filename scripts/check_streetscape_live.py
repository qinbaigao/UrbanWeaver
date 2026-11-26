"""Real streetscape replanning on a frozen city; never modifies its source."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import time

from cityg.agents.streetscape import StreetscapeAgent
from cityg.serialization import city_from_dict, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.run_provenance import source_snapshot
from run_analysis44 import read
from run_edit_method_pilot import RecordedService


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base-url',required=True)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),a.output/'source_provenance.json')
    before=hashlib.sha256(a.city.read_bytes()).hexdigest()
    if a.city.suffix=='.gz':
        with gzip.open(a.city,'rt') as stream:payload=json.load(stream)
    else:
        payload=read(a.city)
    city=city_from_dict(payload)
    endpoint=ModelEndpoint(base_url=a.base_url,model='cityg-llm',timeout_s=180,
                           max_tokens=6144,seed=611,enable_thinking=False)
    service=RecordedService(OpenAICompatibleService(endpoint),a.output/'all_model_calls.json')
    row={'endpoint':a.base_url,'source_sha256':before,'completed':False}
    started=time.monotonic()
    try:
        result=StreetscapeAgent(service,max_calls=3).plan(city)
        save_json(result.trace_dict(),a.output/'streetscape_trace.json')
        row.update(completed=True,diagnostics=result.diagnostics,roads=len(result.program.segments))
    except Exception as exc:
        row['error']=f'{type(exc).__name__}: {exc}'
    row.update(elapsed_s=time.monotonic()-started,model_calls=len(service.calls),
        source_unchanged=before==hashlib.sha256(a.city.read_bytes()).hexdigest(),
        usage={k:sum(c.get('completion',{}).get('usage',{}).get(k,0) for c in service.calls)
               for k in ('prompt_tokens','completion_tokens')})
    save_json(row,a.output/'summary.json')
    print(row,flush=True)
    return 0 if row['completed'] and row['source_unchanged'] else 1


if __name__=='__main__':raise SystemExit(main())
