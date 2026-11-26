import contextlib
import io
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from cityg.progress import progress, progress_scope, recorded_event, _interval


ROOT = Path(__file__).resolve().parents[1]


class ProgressTests(unittest.TestCase):
    def test_disabled_is_silent(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {'CITYG_PROGRESS': 'false'}), contextlib.redirect_stdout(stream):
            with progress_scope('test'):
                progress('test', 'hello')
        self.assertEqual(stream.getvalue(), '')

    def test_summaries_are_bounded_and_do_not_dump_event_payload(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {'CITYG_PROGRESS': 'true'}), contextlib.redirect_stdout(stream):
            progress('test', 'first\nsecond\x1b', value='x'*1000)
            recorded_event('requirement', 'accepted', {
                'building_count': 4, 'prompt': 'private prompt', 'error': 'private response'})
        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertNotIn('\x1b', lines[0])
        self.assertLess(len(lines[0]), 300)
        self.assertIn('building_count=4', lines[1])
        self.assertNotIn('private', stream.getvalue())

    def test_heartbeat_stops_and_exceptions_propagate(self):
        seen = threading.Event()
        messages = []
        def capture(scope, text):
            messages.append(text)
            if '仍在运行' in text:
                seen.set()
        with patch.dict(os.environ, {'CITYG_PROGRESS': 'true'}), \
             patch('cityg.progress._write', side_effect=capture), \
             patch('cityg.progress._interval', return_value=.01):
            with self.assertRaisesRegex(RuntimeError, 'original failure'):
                with progress_scope('test'):
                    progress('compile', 'busy')
                    self.assertTrue(seen.wait(2))
                    raise RuntimeError('original failure')
        self.assertTrue(any('异常退出' in x for x in messages))
        self.assertFalse(any(t.name == 'cityg-progress' for t in threading.enumerate()))

    def test_invalid_interval_is_safe_and_has_a_minimum(self):
        for value, expected in [('bad', 30), ('nan', 30), ('inf', 30), ('0', 5), ('45', 45)]:
            with patch.dict(os.environ, {'CITYG_PROGRESS_INTERVAL': value}):
                self.assertEqual(_interval(), expected)

    def test_broken_terminal_does_not_break_algorithm(self):
        with patch.dict(os.environ, {'CITYG_PROGRESS': 'true'}), \
             patch('builtins.print', side_effect=BrokenPipeError):
            progress('test', 'ignored')

    def test_real_coordinator_progress_does_not_change_model_calls(self):
        from test_closed_loop import FakeService, coordinator, responses
        services = [FakeService(responses()), FakeService(responses())]
        statuses = []
        with tempfile.TemporaryDirectory() as directory:
            for index, value in enumerate(('false', 'true')):
                stream = io.StringIO()
                with patch.dict(os.environ, {'CITYG_PROGRESS':value}), contextlib.redirect_stdout(stream):
                    result = coordinator(services[index]).run('two buildings', Path(directory)/str(index))
                statuses.append(result.run.status)
                if value == 'true':
                    self.assertIn('status=success', stream.getvalue())
                    self.assertIn('[城市布局] 开始', stream.getvalue())
                else:
                    self.assertNotIn('[cityg-progress]', stream.getvalue())
        self.assertEqual(statuses, ['success', 'success'])
        self.assertEqual(services[0].calls, services[1].calls)


class PipelineProgressTests(unittest.TestCase):
    def run_stub(self, root, agent_code=0, review_code=0, enabled=True):
        fake = root/'python'
        fake.write_text(f'''#!{sys.executable}
import os, pathlib, sys
args=sys.argv[1:]
if 'agent-build' in args:
 assert args[args.index('--max-total-tokens')+1]=='0'
 assert args[args.index('--max-tokens')+1]=='6144'
stage='agent-build' if 'agent-build' in args else 'adaptive-review'
print('detailed-debug-output',flush=True)
if os.environ.get('CITYG_PROGRESS')=='true':
 print('[cityg-progress] [test] '+stage,flush=True)
output=pathlib.Path(args[args.index('--output')+1])
if stage=='agent-build':
 (output/'final/openusd').mkdir(parents=True,exist_ok=True)
 (output/'final/openusd/city.json').write_text('{{}}')
sys.exit(int(os.environ.get('FAKE_AGENT_EXIT' if stage=='agent-build' else 'FAKE_REVIEW_EXIT','0')))
''')
        fake.chmod(0o755)
        curl = root/'curl'
        curl.write_text('#!/bin/sh\nexit 0\n')
        curl.chmod(0o755)
        registry = root/'registry.json'
        registry.write_text('{}')
        config = root/'config.env'
        config.write_text(f'''PYTHON_BIN={fake}
ASSET_REGISTRY={registry}
ASSET_GENERATION_ENABLED=false
INCOMING_ASSET_CURATION_ENABLED=false
OUTDOOR_ASSET_PACK_ENABLED=false
FACADE_ASSET_SYSTEM_ENABLED=false
INCLUDE_INTERIORS=false
CITYG_PROGRESS={'true' if enabled else 'false'}
''')
        env = {**os.environ, 'PATH':str(root)+os.pathsep+os.environ['PATH'],
               'CITYG_CONFIG':str(config), 'FAKE_AGENT_EXIT':str(agent_code),
               'FAKE_REVIEW_EXIT':str(review_code)}
        output = root/'output'
        result = subprocess.run(['bash', str(ROOT/'scripts/run_cityg_pipeline.sh'), 'test city', str(output)],
                                env=env, text=True, capture_output=True, timeout=15)
        return result, output

    def test_main_script_shows_only_summaries_and_keeps_full_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            result, output = self.run_stub(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('[cityg-progress] [test] agent-build', result.stdout)
            self.assertIn('[cityg-progress] [test] adaptive-review', result.stdout)
            self.assertNotIn('detailed-debug-output', result.stdout)
            for stage in ('agent_build', 'adaptive_review'):
                self.assertIn('detailed-debug-output', (output/f'logs/{stage}.log').read_text())

    def test_main_script_failure_partial_and_quiet_modes(self):
        for agent, review, enabled, expected in [(7, 0, True, 2), (0, 9, True, 2),
                                                (3, 0, True, 3), (0, 0, False, 0)]:
            with self.subTest(agent=agent, review=review, enabled=enabled), tempfile.TemporaryDirectory() as directory:
                result, _ = self.run_stub(Path(directory), agent, review, enabled)
                self.assertEqual(result.returncode, expected, result.stderr)
                if agent == 7:
                    self.assertIn('agent-build failed with exit code 7', result.stderr)
                    self.assertNotIn('[test] adaptive-review', result.stdout)
                if review == 9:
                    self.assertIn('adaptive-review failed with exit code 9', result.stderr)
                if not enabled:
                    self.assertNotIn('[cityg-progress]', result.stdout)

    def test_line_arrives_before_producer_exits(self):
        source = (ROOT/'scripts/run_cityg_pipeline.sh').read_text()
        body = source.split('run_logged() {', 1)[1].split('\n}\n', 1)[0]
        script = 'set -o pipefail\nrun_logged() {' + body + '\n}\nrun_logged "$1" "$2" -u -c "$3"'
        producer = "import time; print('[cityg-progress] ready',flush=True); time.sleep(2)"
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.Popen(['bash', '-c', script, 'test', str(Path(directory)/'log'),
                                        sys.executable, producer], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(timeout=1), 'progress was buffered until exit')
                self.assertIn(b'[cityg-progress] ready', process.stdout.readline())
                self.assertIsNone(process.poll())
                process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
