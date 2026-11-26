"""Run the reproducible offline method development pilot; never starts model services."""
import argparse
import json
from pathlib import Path

from cityg.evaluation.method_pilot import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/method_pilot.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(json.loads(args.config.read_text()), args.output)
    print(json.dumps({k: report[k] for k in ('run_status', 'runner_ok', 'comparisons')}, indent=2))
    return 0 if report['runner_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
