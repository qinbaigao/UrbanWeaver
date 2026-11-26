"""Real-model paired repair pilot. Requires an already-running model endpoint."""
import argparse
import json
from pathlib import Path
from cityg.evaluation.model_repair_pilot import run

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('configs/model_method_pilot.json'))
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(json.loads(args.config.read_text()), args.output), indent=2))
