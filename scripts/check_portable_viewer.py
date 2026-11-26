"""Bounded, headless loading smoke test; never opens a desktop browser."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from cityg.serialization import save_json


async def check(url, output, timeout, views=(), require_assets=False, canvas_only=False, width=1200, height=800, task_replay=False):
    from playwright.async_api import async_playwright
    messages = []
    failure = asyncio.Event()
    result = {'url': url, 'profile': 'navigation', 'ready': False, 'messages': messages}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=[
            '--disable-dev-shm-usage', '--use-angle=swiftshader',
            '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        page = await browser.new_page(viewport={'width': width, 'height': height})
        def message(kind, text):
            messages.append({'kind': kind, 'text': text})
            print(kind, text, flush=True)
            if kind in {'pageerror', 'crash'} or 'SyntaxError' in text or 'RangeError' in text:
                failure.set()
        page.on('pageerror', lambda error: message('pageerror', str(error)))
        page.on('console', lambda msg: message('console', msg.text) if msg.type == 'error' else None)
        page.on('crash', lambda _: message('crash', 'Renderer process crashed'))
        await page.add_init_script("""
            window.__CITYG_RENDER_PROFILE__ = 'navigation';
            const originalJson = Response.prototype.json;
            Response.prototype.json = async function(...args) {
                try { return await originalJson.apply(this, args); }
                catch (error) {
                    console.error(`JSON decode failed: ${this.url}; bytes=${this.headers.get('content-length')}; ${error}`);
                    throw error;
                }
            };
        """)
        ready_task = failure_task = None
        try:
            await page.goto(url, wait_until='commit', timeout=60000)
            if canvas_only:
                # Review captures need the full landscape frame, not the narrow
                # canvas left between two inspector panels. This is page-local.
                await page.add_style_tag(content='''
                    #app { display: block !important; }
                    .topbar, .panel { display: none !important; }
                    .viewport-actions, .status-strip, #legend, #toast, #loading { display: none !important; }
                    #viewport { width: 100vw !important; height: 100vh !important; }
                ''')
                result['canvas_only'] = True
            ready_task = asyncio.create_task(page.wait_for_function(
                'window.citygObservation && window.citygObservation.ready', timeout=timeout*1000))
            failure_task = asyncio.create_task(failure.wait())
            completed, _ = await asyncio.wait([ready_task, failure_task],
                                               return_when=asyncio.FIRST_COMPLETED)
            if ready_task in completed:
                await ready_task
                result['ready'] = True
                await page.screenshot(path=str(output/'navigation.png'), timeout=30000)
                result['views'] = []
                for view in views:
                    step = {'view_id': view['view_id'], 'spec': view}
                    result['views'].append(step)
                    print('view_start', view['view_id'], flush=True)
                    canvas_box = await page.locator('#scene-canvas').bounding_box()
                    if not canvas_box:
                        raise RuntimeError('Scene canvas has no capture rectangle')
                    started = time.monotonic()
                    step['view_status'] = await asyncio.wait_for(page.evaluate(
                        '(spec) => window.citygObservation.setView(spec)', view), timeout)
                    print('view_ready', view['view_id'], flush=True)
                    step['assets'] = await asyncio.wait_for(page.evaluate(
                        '(ms) => window.citygObservation.waitForAssets({timeout_ms: ms, quiet_ms: 100})',
                        timeout*1000), timeout+5)
                    if not step['assets']['ready']:
                        raise RuntimeError(f"Assets not ready: {step['assets']}")
                    print('assets_ready', view['view_id'], step['assets'].get('loaded',0), flush=True)
                    if require_assets and view.get('render_profile') in {'presentation','interactive','high_fidelity','prototype_capture','paper_capture'}:
                        assets=step['assets']
                        if (assets.get('expected',0)<=0 or assets.get('loaded',0)!=assets['expected']
                                or assets.get('fallback',0) or assets.get('failed',0)
                                or assets.get('material_textures_failed',0)):
                            raise RuntimeError(f"Real assets required; ready proxies do not count: {assets}")
                    destination = output/f"{view['view_id']}.png"
                    try:
                        data_url = await asyncio.wait_for(page.evaluate(
                            '() => window.citygObservation.captureFrame()'), min(timeout, 30))
                        destination.write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
                        step['capture_method'] = 'canvas_readback'
                    except asyncio.TimeoutError:
                        # Same stable view and asset barrier, using the compositor
                        # when SwiftShader's WebGL readback stalls. Do not alter LOD.
                        print('capture_compositor_fallback', view['view_id'], flush=True)
                        await page.screenshot(path=str(destination), clip=canvas_box, timeout=timeout*1000)
                        step['capture_method'] = 'compositor_after_readback_timeout'
                    step['elapsed_s'] = round(time.monotonic()-started, 3)
                    print('view_end', view['view_id'], step['elapsed_s'], flush=True)
                result['exercise_ok'] = True
                if task_replay:
                    await asyncio.wait_for(page.evaluate('() => window.citygTaskReplay.load()'), timeout)
                    result['task_replay_samples'] = []
                    for seconds in (0, 10, 250, 450, 700, 1e9):
                        await asyncio.wait_for(page.evaluate('(t) => window.citygTaskReplay.seek(t)', seconds), timeout)
                        status = await page.evaluate('() => window.citygTaskReplay.status()')
                        if not status['loaded'] or status['suppressed_count'] < 5:
                            raise RuntimeError('Replay failed to suppress static duplicates')
                        if status.get('robot'):
                            robot=status['robot'];matrix=status['frame']['effector_matrix']
                            if (robot['links']!=26 or robot['meshes']<15
                                or math.dist(robot['effector_position'],[matrix[i][3] for i in range(3)])>1e-5):
                                raise RuntimeError('Rendered Fetch links/FK do not match the checked robot')
                            camera=status.get('camera',{});base=status['frame']['robot_base']
                            yaw=math.radians(status['frame']['robot_yaw_deg'])
                            expected=[base[0]-.8*math.cos(yaw),base[1]-.8*math.sin(yaw),base[2]+1.35]
                            if (status.get('camera_mode')!='chase'
                                or math.dist(camera.get('position',[0,0,0]),expected)>1e-5
                                or camera.get('up')!=[0,0,1]):
                                raise RuntimeError('Default replay camera is not behind/above the robot')
                        result['task_replay_samples'].append(status)
                    final = result['task_replay_samples'][-1]['frame']
                    obj = next(iter(final['objects'].values()))
                    if final['action'] != 'release' or obj['holder'] is not None or not obj['support']:
                        raise RuntimeError('Replay did not reach the accepted release endpoint')
                    result['task_replay_assets'] = await asyncio.wait_for(page.evaluate(
                        '(ms) => window.citygObservation.waitForAssets({timeout_ms:ms,quiet_ms:100})',timeout*1000),timeout+5)
                    if not result['task_replay_assets']['ready']:
                        raise RuntimeError('Final replay assets did not finish loading')
                    await page.screenshot(path=str(output/'task_final.png'), timeout=30000)
                    if result['task_replay_samples'][-1].get('robot'):
                        milestones=await page.evaluate('() => window.citygTaskReplay.milestones()')
                        for action in ('attach','stow_object','door','transit:enter','transit:ride'):
                            if action not in milestones:continue
                            await page.evaluate('(t) => window.citygTaskReplay.seek(t)',milestones[action])
                            assets=await asyncio.wait_for(page.evaluate(
                                '(ms) => window.citygObservation.waitForAssets({timeout_ms:ms,quiet_ms:100})',timeout*1000),timeout+5)
                            if not assets['ready']:raise RuntimeError('Robot interaction screenshot assets not ready')
                            await page.screenshot(path=str(output/f"task_{action.replace(':','_')}.png"),timeout=30000)
                        result['robot_milestones']=milestones
                        for mode in ('robot','context','chase'):
                            await page.locator('[data-camera]').select_option(mode)
                            status=await page.evaluate('() => window.citygTaskReplay.status()')
                            if status['camera_mode']!=mode:
                                raise RuntimeError('Replay camera selector did not update')
                        result['task_replay_cameras_ok']=True
                    await page.evaluate('() => window.citygTaskReplay.seek(0)')
                    await page.locator('[data-play]').click()
                    await page.wait_for_function('window.citygTaskReplay.status().seconds > 0.2',timeout=10000)
                    await page.locator('[data-play]').click()
                    playing = await page.evaluate('() => window.citygTaskReplay.status()')
                    if playing['playing'] or playing['seconds']<=0:
                        raise RuntimeError('Replay play/pause did not advance then pause')
                    result['task_replay_play_pause_ok'] = True
                    await page.evaluate('() => window.citygTaskReplay.exit()')
                    if (await page.evaluate('() => window.citygTaskReplay.status()'))['suppressed_count'] != 0:
                        raise RuntimeError('Replay exit left hidden static geometry')
                    result['task_replay_ok'] = True
            else:
                result['error'] = 'Viewer initialization failed; see messages'
        except Exception as error:
            result['error'] = f'{type(error).__name__}: {error}'
            result['exercise_ok'] = False
        finally:
            for task in (ready_task, failure_task):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(t for t in (ready_task, failure_task) if t is not None),
                                 return_exceptions=True)
            save_json(result, output/'viewer_smoke.json')
            save_json({'policy': 'viewer_generation_scoped_asset_barrier_v1', 'views': {
                step['view_id']: {**step['assets'], 'view_status': step.get('view_status', {})}
                for step in result.get('views', []) if step.get('assets')
            }}, output/'asset_load_status.json')
            await browser.close()
    return result


def exercise_views(viewer):
    city = json.loads((viewer/'scene/city.json').read_text())
    bounds = city['bounds']
    x, y = (bounds['min_x']+bounds['max_x'])/2, (bounds['min_y']+bounds['max_y'])/2
    extent = max(bounds['max_x']-bounds['min_x'], bounds['max_y']-bounds['min_y'])
    overview = {'kind': 'city_overview', 'mode': 'overview', 'target_entity_ids': [],
                'camera_position': [x+extent*.8, y-extent*.8, extent*.75],
                'look_at': [x,y,0], 'appearance': 'presentation', 'auto_cutaway': False}
    views = [{**overview, 'view_id': 'overview_review', 'render_profile': 'review'}]
    buildings = [b for d in city['districts'] for p in d['parcels'] for b in p['buildings']]
    for index, b in enumerate([buildings[0], buildings[-1]]):
        f=b['footprint']; bx, by=(f['min_x']+f['max_x'])/2, (f['min_y']+f['max_y'])/2
        width=max(f['max_x']-f['min_x'],f['max_y']-f['min_y'])
        height=max((floor.get('elevation_m',0)+floor.get('height_m',3) for floor in b['floors']),default=10)
        offset=max(width*1.8,height*.9)
        views.append({'view_id': f'building_{index}', 'kind':'building_exterior', 'mode':'building',
                      'target_entity_ids':[b['id']], 'render_profile':'review', 'auto_cutaway':False,
                      # Stay above neighboring towers; a long diagonal street
                      # camera can otherwise land inside an adjacent building.
                      'camera_position':[bx+offset,by-offset,max(height*2.2,100)], 'look_at':[bx,by,height*.45]})
        views.append({**overview,'view_id':f'navigation_return_{index}','render_profile':'navigation'})
    views.append({**overview,'view_id':'overview_presentation','render_profile':'presentation'})
    return views


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=180)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--exercise', action='store_true', help='Check two local buildings and quality transitions')
    selection.add_argument('--plan', type=Path, help='Capture selected_views from a saved observation plan')
    parser.add_argument('--skip-presentation', action='store_true', help='Keep the exercised views on the headless review profile')
    parser.add_argument('--require-assets', action='store_true', help='Require real GLBs, not ready procedural fallbacks, in textured views')
    parser.add_argument('--canvas-only', action='store_true', help='Hide inspector panels for full-frame capture')
    parser.add_argument('--task-replay', action='store_true', help='Load, seek and exit a packaged accepted transport replay')
    parser.add_argument('--width', type=int, default=1200)
    parser.add_argument('--height', type=int, default=800)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('Timeout must be positive')
    if not (320 <= args.width <= 8192 and 240 <= args.height <= 8192):
        parser.error('Invalid capture dimensions')
    if not (args.viewer/'viewer-config.json').is_file():
        parser.error('Portable export is not complete')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Output must be absent or empty')
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(
        SimpleHTTPRequestHandler, directory=str(args.viewer.resolve())))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        views = exercise_views(args.viewer) if args.exercise else ()
        if args.plan:
            views = json.loads(args.plan.read_text())['selected_views']
            if not isinstance(views, list) or not views:
                raise ValueError('Observation plan must contain a nonempty selected_views list')
        if args.skip_presentation:
            views = [view for view in views if view.get('render_profile') != 'presentation']
        result = asyncio.run(check(f'http://127.0.0.1:{server.server_port}/', args.output, args.timeout, views, args.require_assets,
                                  args.canvas_only, args.width, args.height, args.task_replay))
        print(result, flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    if not result.get('exercise_ok'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
