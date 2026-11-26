"""Checkpoint a large exterior plan before expensive compilation.

Compile a successful planned_city.json with resume_exterior_checkpoint.py.
No source geometry checks are bypassed and no desktop browser is opened.
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import time
from pathlib import Path

from cityg.agents import RequirementAgent, HierarchicalPlanningAgent, AgentGenerationError
from cityg.morphology import realization_report, contract_issues
from cityg.planning import BaselineCityPlanner
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.validation import CityValidator
from run_architecture_smoke import TracedService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--online', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Output must be absent or empty')
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.spec.read_text())
    spec = CitySpec.from_dict(source)
    save_json(source, output/'input_spec.json')
    started = time.monotonic()
    with (output/'progress.jsonl').open('w') as log, (output/'stacks.log').open('w') as stacks:
        def event(stage, **detail):
            record = {'stage': stage, 'elapsed_s': round(time.monotonic()-started, 3), **detail}
            line = json.dumps(record)
            print(line, flush=True)
            log.write(line+'\n')
            log.flush()
        faulthandler.dump_traceback_later(120, repeat=True, file=stacks)
        try:
            planner = BaselineCityPlanner()
            if args.online:
                service = TracedService(ModelEndpoint(base_url='http://127.0.0.1:8000/v1',
                    model='cityg-llm', max_tokens=8192, timeout_s=300, temperature=.2,
                    seed=source['seed']), output)
                instruction = ('只生成城市室外外观，不生成可进入的室内。'
                    '请严格保留以下结构化需求，包括建筑数量、全部分区及其外壳组合、'
                    'landscape_adaptive道路和河流形态参数。'
                    'Urban Agent 不得改回普通网格。分区外壳优先于共享Building profile。'
                    '住宅与公共建筑以中低层为主，商业区有高层与少量地标，避免统一层数。'
                    '不要把矩形层数变化算作新的轮廓类型。房间仅作低成本语义占位。'
                    '配置：'+json.dumps(source, ensure_ascii=False))
                save_json({'instruction': instruction}, output/'instruction.json')
                event('requirement_start')
                parsed = RequirementAgent(service, model_id='cityg-llm').parse(instruction)
                spec = parsed.spec
                save_json(parsed.trace_dict(), output/'requirement_trace.json')
                event('hierarchy_start')
                hierarchy = HierarchicalPlanningAgent(service, model_id='cityg-llm',
                    max_calls_per_agent=8).plan(spec)
                save_json(hierarchy.program, output/'hierarchical_program.json')
                save_json(hierarchy.trace_dict(), output/'hierarchy_trace.json')
                planner = ProgrammedCityPlanner(hierarchy.program,
                    appearance_program=hierarchy.appearance.program if hierarchy.appearance else None)
            save_json(spec, output/'requested_spec.json')
            event('layout_start')
            city = planner.plan(spec)
            event('validation_start', buildings=len(list(city.iter_buildings())))
            report = CityValidator().validate(city)
            save_json(report.to_dict(), output/'validation_report.json')
            save_json({'online': args.online, 'realized': realization_report(city),
                'intent_issues': contract_issues(city), 'validation': report.to_dict(),
                'compiled': False, 'interiors_requested': False}, output/'morphology_report.json')
            # Preserve failed candidates for diagnosis, but never call them ready.
            event('saving_checkpoint', ok=report.ok)
            save_json(city, output/('planned_city.json' if report.ok else 'rejected_city.json'))
            if not report.ok:
                raise RuntimeError(f'City validation failed: {len(report.errors)} errors; see report')
            event('plan_ready')
        except AgentGenerationError as error:
            from dataclasses import asdict
            save_json({'error': str(error), 'attempts': [asdict(a) for a in error.attempts]},
                      output/'agent_failure.json')
            event('failed', error=str(error))
            raise
        except Exception as error:
            event('failed', error=str(error))
            raise
        finally:
            faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':
    main()
