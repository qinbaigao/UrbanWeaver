"""Opt-in terminal summaries; never feed progress back into planning decisions."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math
import os
import re
import threading
import time


PREFIX = '[cityg-progress]'
_current = ContextVar('cityg_progress', default=None)
_output_lock = threading.Lock()

STAGES = {
    'requirement': '需求分析', 'prototype_selection': '城市原型选择',
    'hierarchy_urban': '城市布局', 'hierarchy_skyline': '高度与天际线',
    'hierarchy_building': '建筑规划', 'hierarchy_floor': '楼层规划',
    'hierarchy_appearance': '外观风格', 'planning': '布局实例化与楼层适配',
    'prototype_adaptation': '楼层与房间原型适配',
    'functional_completion': '功能与陈设补齐',
    'functional_configuration': '合理功能配置',
    'planning_streetscape': '街景规划', 'validation': '语义与几何校验',
    'repair': '约束修复', 'compilation': '场景编译',
    'viewer': '便携 Viewer 导出', 'complete': '生成结果',
}
EVENTS = {
    'run_started': '任务已创建', 'urban_reference_selected': '城市原型已选择',
    'requirement_accepted': '需求已解析', 'urban_program_accepted': '城市布局已接受',
    'skyline_program_accepted': '天际线方案已接受',
    'building_program_accepted': '建筑方案已接受',
    'hierarchy_accepted': '层级方案已接受', 'city_planned': '城市布局已实例化',
    'appearance_program_accepted': '外观方案已接受',
    'interior_capability_reserved': '已预留精细室内范围',
    'building_floor_programs_accepted': '建筑专属楼层规划已处理',
    'adaptive_refinements_applied': '局部个性化已处理',
    'issues_routed': '已确定问题处理路径',
    'streetscape_program_accepted': '街景方案已接受',
    'streetscape_agent_fallback': '街景模型方案失败，使用确定性回退',
    'functional_completion_checked': '有界陈设补齐已完成',
    'functional_configuration_checked': '有界功能配置已完成',
    'prototype_step': '房间原型处理', 'prototype_adaptation_completed': '原型适配结束',
    'validation_completed': '校验完成', 'repair_committed': '修复已提交',
    'simulation_compiled': '仿真场景已编译', 'viewer_exported': 'Viewer 已导出',
    'run_finished': '生成流程结束', 'requirement_checks_failed': '需求验收未通过',
}


def enabled():
    return os.environ.get('CITYG_PROGRESS', '').lower() in {'1', 'true', 'yes', 'on'}


def _clean(value):
    # Keep model-derived identifiers on one bounded terminal line. No prompts,
    # request bodies, credentials, raw completions, or arbitrary event dicts.
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', str(value))[:180]


def _write(scope, message):
    with _output_lock:
        try:
            print(f'{PREFIX} [{time.strftime("%H:%M:%S")}] [{_clean(scope)}] {message}', flush=True)
        except (OSError, ValueError):
            # A closed terminal must not turn a valid generation into failure.
            pass


def progress(scope, message, **fields):
    if not enabled():
        return
    text = _clean(message)
    if fields:
        text += ' | ' + ' '.join(f'{_clean(k)}={_clean(v)}' for k, v in fields.items())
    state = _current.get()
    if state is not None:
        with state['lock']:
            state['last'] = (scope, text)
    _write(scope, text)


def stage_started(stage):
    progress(STAGES.get(stage, stage), '开始')


def recorded_event(stage, event, detail):
    fields = {k: v for k, v in detail.items() if k in {
        'status', 'attempts', 'building_count', 'floor_count', 'room_count',
        'zone_count', 'model_calls', 'disclosures', 'prototype_id',
        'error_count', 'warning_count', 'repair_round', 'round',
        'buildings', 'floors', 'rooms', 'errors', 'warnings', 'artifact_count', 'output',
        'planned_buildings', 'failed_buildings', 'skipped_buildings',
    } and isinstance(v, (str, int, float, bool))}
    if event == 'prototype_step':
        parts = detail.get('detail', [])
        # Rejected prototypes retain the detailed exception in events.jsonl.
        fields = dict(zip(('step', 'room'), parts[:2]))
    progress(STAGES.get(stage, stage), EVENTS.get(event, event), **fields)


def _interval():
    try:
        value = float(os.environ.get('CITYG_PROGRESS_INTERVAL', '30'))
        return max(5.0, value) if math.isfinite(value) else 30.0
    except ValueError:
        return 30.0


@contextmanager
def progress_scope(label):
    if not enabled():
        yield
        return
    started = time.monotonic()
    state = {'lock': threading.Lock(), 'last': (label, '初始化')}
    token = _current.set(state)
    stopped = threading.Event()

    def heartbeat():
        while not stopped.wait(_interval()):
            with state['lock']:
                scope, text = state['last']
            _write(label, f'仍在运行，已耗时 {time.monotonic()-started:.0f}s；最近进度：[{_clean(scope)}] {text}')

    worker = threading.Thread(target=heartbeat, name='cityg-progress', daemon=True)
    progress(label, '开始')
    worker.start()
    try:
        yield
    except BaseException as exc:
        progress(label, '异常退出；详情见日志', error_type=type(exc).__name__)
        raise
    finally:
        stopped.set()
        worker.join(timeout=1)
        progress(label, '阶段结束', elapsed_s=f'{time.monotonic()-started:.1f}')
        _current.reset(token)


def report_run(label):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with progress_scope(label):
                return function(*args, **kwargs)
        return wrapped
    return decorate
