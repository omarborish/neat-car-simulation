"""Local transport integration over real cars and a single runtime owner."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest

from aiohttp import ClientSession, WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer
from runtime import Runtime
from tracks import ROOT, load_track
from workspace_temp import WorkspaceTemp


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Windows CPU scheduling during a real 100-car run can exceed the
        # debug logger's 100 ms threshold without a coroutine blocking.
        asyncio.get_running_loop().slow_callback_duration = 2
        self.assertIsNotNone(importlib.util.find_spec('server'),
                             'Local simulation server is not implemented')
        import server
        self.module = server
        self.folder = WorkspaceTemp()
        self.runtime = Runtime(Path(self.folder.name))
        self.event = asyncio.Event()
        self.app = server.create_app(self.runtime, self.event)
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()
        self.origin = str(self.client.make_url('/')).rstrip('/')
        self.headers = {'Origin': self.origin}
        self.addAsyncCleanup(self.client.close)
        self.addCleanup(self.folder.cleanup)
        for _ in range(100):
            response = await self.client.get('/api/state')
            if response.status == 200:
                self.initial = await response.json()
                break
            await asyncio.sleep(.01)
        else:
            self.fail('worker did not publish its first snapshot')

    async def command(self, command, **fields):
        response = await self.client.post('/api/command', json={'command': command, **fields},
                                          headers=self.headers)
        self.assertEqual(response.status, 200, await response.text())
        result = await response.json()
        self.assertTrue(result['ok'], result)
        return result['snapshot']

    async def test_identity_state_and_real_streamed_positions(self):
        identity = await (await self.client.get('/api/identity')).json()
        self.assertEqual(identity['application_id'], 'neat-car-simulation')
        self.assertEqual(identity['protocol'], 1)
        self.assertEqual(identity['project_root'], str(ROOT.resolve()))
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        first = await ws.receive_json(timeout=2)
        later = await ws.receive_json(timeout=2)
        self.assertEqual(first['schema_version'], 1)
        self.assertNotEqual(first['cars'][0]['position'], later['cars'][0]['position'])
        self.assertGreater(later['effective_step_rate'], 0)
        await ws.close()

    async def test_commands_validation_pause_and_reconnect_preserve_session(self):
        paused = await self.command('pause')
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        self.assertEqual((await ws.receive_json(timeout=2))['session_id'], paused['session_id'])
        await ws.close()
        await asyncio.sleep(.12)
        state = await (await self.client.get('/api/state')).json()
        self.assertEqual(state['cars'], paused['cars'])
        self.assertEqual(state['effective_step_rate'], 0)
        response = await self.client.post('/api/command', json={'command': 'speed', 'multiplier': 2}, headers=self.headers)
        self.assertEqual(response.status, 400)
        self.assertFalse((await response.json())['ok'])
        changed = await self.command('appearance', color='purple', sensors=False)
        self.assertEqual(changed['session_id'], paused['session_id'])
        self.assertEqual(changed['cars'][0]['position'], paused['cars'][0]['position'])
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        self.assertEqual((await ws.receive_json(timeout=2))['appearance']['color'], 'purple')
        await ws.close()
        await self.command('resume')

    async def test_malformed_oversized_host_and_origin_requests(self):
        for data, status in [('not json', 400), ('[]', 400), ('{"command":NaN}', 400),
                             ('[' * 1500 + ']' * 1500, 400), ('x' * 32769, 413)]:
            response = await self.client.post('/api/command', data=data, headers=self.headers)
            self.assertEqual(response.status, status)
        for headers in [{'Origin': 'https://evil.example'}, {'Origin': 'http://['}, {},
                        {'Origin': self.origin, 'Host': 'evil.example'}]:
            response = await self.client.post('/api/command', json={'command': 'pause'}, headers=headers)
            self.assertEqual(response.status, 403)
        response = await self.client.get('/api/identity', headers={'Host': 'evil.example'})
        self.assertEqual(response.status, 403)
        await self.command('apply_settings', settings={'population': 100})
        response = await self.client.post('/api/command', json={'command': 'z' * 30000}, headers=self.headers)
        self.assertEqual(response.status, 400)
        self.assertLessEqual(len(await response.read()), 32768)
        self.assertEqual((await self.client.get('/api/state')).status, 200)

    async def test_static_allowlist_and_exact_geometry_catalog(self):
        self.assertEqual((await self.client.get('/')).status, 200)
        self.assertEqual((await self.client.get('/assets/tracks/map.png')).status, 200)
        self.assertEqual((await self.client.get('/assets/cars/carred.png')).status, 200)
        for path in ['/assets/circuits/monza.json', '/assets/saved/classic.json',
                     '/assets/tracks/%2e%2e%2f%2e%2e%2frequirements.txt', '/web/requirements.txt']:
            self.assertEqual((await self.client.get(path)).status, 404, path)
        catalog = await (await self.client.get('/api/catalog')).json()
        self.assertEqual(len(catalog['tracks']), 13)
        monza = next(track for track in catalog['tracks'] if track['id'] == 'monza')
        self.assertEqual(monza['geometry'], json.loads(json.dumps(load_track('monza').geometry)))
        await self.command('apply_settings', settings={'population': 10, 'road_width': 90})
        catalog = await (await self.client.get('/api/catalog')).json()
        self.assertEqual(catalog['road_width'], 90)
        self.assertEqual(next(t for t in catalog['tracks'] if t['id'] == 'silverstone')['geometry']['road_width'], 90)

    async def test_slow_and_disconnected_clients_do_not_stall_or_accumulate(self):
        await self.command('apply_settings', settings={'population': 100})
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        first = await ws.receive(timeout=2)
        self.assertEqual(first.type, WSMsgType.TEXT)
        self.assertLessEqual(len(first.data.encode()), 32768)
        initial = await (await self.client.get('/api/state')).json()
        await asyncio.sleep(.25)
        state_response = await self.client.get('/api/state')
        self.assertLessEqual(len(await state_response.read()), 32768)
        state = await state_response.json()
        self.assertNotEqual(initial['cars'], state['cars'])
        await ws.close()
        for _ in range(100):
            if not self.app[self.module.SERVICE_KEY].sockets:
                break
            await asyncio.sleep(.02)
        self.assertFalse(self.app[self.module.SERVICE_KEY].sockets)

    async def test_shutdown_stops_worker_sockets_and_releases_listener(self):
        service = self.app[self.module.SERVICE_KEY]
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        await ws.receive_json(timeout=2)
        port = self.client.server.port
        response = await self.client.post('/api/shutdown', headers=self.headers)
        self.assertEqual(response.status, 200)
        await asyncio.wait_for(self.event.wait(), 2)
        for _ in range(100):
            if not service.worker.is_alive():
                break
            await asyncio.sleep(.01)
        self.assertFalse(service.worker.is_alive())
        await ws.close()
        await self.client.close()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', port))

    async def test_websocket_commands_rejected_and_oversized_closed(self):
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        await ws.receive_json(timeout=2)
        await ws.send_str('{"command":"pause"}')
        message = await ws.receive(timeout=2)
        self.assertIn(message.type, (WSMsgType.CLOSE, WSMsgType.CLOSED))
        await ws.close()
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        await ws.receive_json(timeout=2)
        await ws.send_str('x' * 32769)
        for _ in range(10):
            message = await ws.receive(timeout=2)
            if message.type != WSMsgType.TEXT:
                break
        self.assertIn(message.type, (WSMsgType.CLOSE, WSMsgType.CLOSED))
        await ws.close()

    async def test_requested_speed_and_measured_rate(self):
        await self.command('pause')
        slow = await self.command('speed', multiplier=1)
        self.assertEqual(slow['step_rate'], 60)
        self.assertEqual(slow['effective_step_rate'], 0)
        await self.command('resume')
        await asyncio.sleep(.3)
        slow = await (await self.client.get('/api/state')).json()
        self.assertGreater(slow['effective_step_rate'], 20)
        await self.command('pause')
        fast = await self.command('speed', multiplier=4)
        self.assertEqual(fast['step_rate'], 240)
        await self.command('resume')
        await asyncio.sleep(.3)
        fast = await (await self.client.get('/api/state')).json()
        self.assertGreater(fast['effective_step_rate'], slow['effective_step_rate'] * 2)
        self.assertLess(fast['effective_step_rate'], 260)

    async def test_blocked_writer_times_out_without_stalling_physics(self):
        ws = await self.client.ws_connect('/ws', headers=self.headers)
        await ws.receive_json(timeout=2)
        server_ws = next(iter(self.app[self.module.SERVICE_KEY].sockets))
        entered = asyncio.Event()

        async def blocked_write(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        server_ws.send_str = blocked_write
        await asyncio.wait_for(entered.wait(), 1)
        before = await (await self.client.get('/api/state')).json()
        await asyncio.sleep(.2)
        after = await (await self.client.get('/api/state')).json()
        self.assertNotEqual(before['cars'][0]['position'], after['cars'][0]['position'])
        for _ in range(100):
            if not self.app[self.module.SERVICE_KEY].sockets:
                break
            await asyncio.sleep(.02)
        self.assertFalse(self.app[self.module.SERVICE_KEY].sockets)
        await ws.close()


class WorkerOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_serve_shutdown_releases_port_without_external_cleanup(self):
        asyncio.get_running_loop().slow_callback_duration = 2
        self.assertIsNotNone(importlib.util.find_spec('server'), 'Local simulation server is not implemented')
        import server
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        running = asyncio.create_task(server._serve(port, False))
        origin = f'http://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                for _ in range(100):
                    try:
                        async with client.get(origin + '/api/identity') as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    await asyncio.sleep(.02)
                async with client.post(origin + '/api/shutdown', headers={'Origin': origin}) as response:
                    self.assertEqual(response.status, 200)
            await asyncio.wait_for(running, 3)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', port))
        finally:
            if not running.done():
                running.cancel()
            await asyncio.gather(running, return_exceptions=True)

    async def test_fixed_ticks_bound_catchup_and_discard_timing_backlog(self):
        asyncio.get_running_loop().slow_callback_duration = 2
        self.assertIsNotNone(importlib.util.find_spec('server'), 'Local simulation server is not implemented')
        import server
        folder = WorkspaceTemp()
        self.addCleanup(folder.cleanup)
        ticks = []
        delayed = threading.Event()

        class DelayedRuntime(Runtime):
            def step(self):
                if not delayed.is_set():
                    time.sleep(.15)
                    delayed.set()
                ticks.append(time.monotonic())
                super().step()

        app = server.create_app(lambda: DelayedRuntime(Path(folder.name)))
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        await asyncio.to_thread(delayed.wait, 2)
        await asyncio.sleep(.16)
        await app[server.SERVICE_KEY].stop()
        self.assertGreater(len(ticks), 5)
        # At most five catch-up ticks; the sixth resumes a future deadline.
        self.assertGreater(ticks[5] - ticks[4], .01)
        self.assertLess(len(ticks), 19)

    async def test_worker_owned_startup_and_generation_keep_http_responsive(self):
        asyncio.get_running_loop().slow_callback_duration = 2
        self.assertIsNotNone(importlib.util.find_spec('server'), 'Local simulation server is not implemented')
        import server
        folder = WorkspaceTemp()
        self.addCleanup(folder.cleanup)
        entered, release = threading.Event(), threading.Event()
        owners = []

        class ObservedRuntime(Runtime):
            def command(self, data):
                owners.append(threading.get_ident())
                if data['command'] == 'restart':
                    entered.set()
                    release.wait(2)
                return super().command(data)

            def snapshot(self):
                owners.append(threading.get_ident())
                return super().snapshot()

            def step(self):
                owners.append(threading.get_ident())
                return super().step()

        def factory():
            owners.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return ObservedRuntime(Path(folder.name))

        app = server.create_app(factory)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        self.assertTrue(entered.wait(.2))
        identity = await asyncio.wait_for(client.get('/api/identity'), .5)
        self.assertEqual(identity.status, 200)
        self.assertEqual((await client.get('/api/state')).status, 503)
        release.set()
        for _ in range(100):
            if (await client.get('/api/state')).status == 200:
                break
            await asyncio.sleep(.01)
        entered.clear()
        release.clear()
        origin = str(client.make_url('/')).rstrip('/')
        command = asyncio.create_task(client.post('/api/command', json={'command': 'restart'}, headers={'Origin': origin}))
        await asyncio.to_thread(entered.wait, .5)
        self.assertEqual((await asyncio.wait_for(client.get('/api/state'), .5)).status, 200)
        service = app[server.SERVICE_KEY]
        pending = [service.submit({'command': 'pause'}) for _ in range(50)]
        with self.assertRaises(server.CommandQueueFull):
            service.submit({'command': 'pause'})
        release.set()
        self.assertEqual((await command).status, 200)
        await asyncio.gather(*(asyncio.wrap_future(future) for future in pending))
        self.assertEqual(len(set(owners)), 1)
        self.assertNotEqual(owners[0], threading.get_ident())


class LauncherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 2
        import server
        self.server = server
        self.assertTrue(hasattr(server, 'default_identity_file'),
                        'Launcher identity persistence and verified reuse are missing')
        self.folder = WorkspaceTemp()
        self.addCleanup(self.folder.cleanup)
        self.identity_file = Path(self.folder.name) / 'identity.json'
        self.tasks = []
        self.addAsyncCleanup(self.stop_servers)

    async def stop_servers(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def test_concurrent_process_launches_share_one_worker_and_stop_completely(self):
        # Independent interpreters, synchronized before discovery. The second
        # spelling resolves through '..'; the junction test covers Windows links.
        target = Path(self.folder.name) / 'concurrent checkout'
        target.mkdir()
        for source in ROOT.glob('*.py'):
            shutil.copy2(source, target)
        for directory in ('assets', 'demos'):
            shutil.copytree(ROOT / directory, target / directory)
        (target / 'alias').mkdir()
        child = '''import asyncio, os, pathlib, time
import server
root = pathlib.Path.cwd().resolve()
tag = os.environ['RACE_TAG']
(root / ('waiting-' + tag)).touch()
while not (root / 'go').exists(): time.sleep(.01)
original = server.create_app
def observed(*args, **kwargs):
    (root / ('worker-' + tag)).touch()
    time.sleep(.3)
    return original(*args, **kwargs)
server.create_app = observed
asyncio.run(server._serve(int(os.environ['RACE_PORT']), False, root / ('mirror-' + tag + '.json')))
'''
        for mode in ('ephemeral', 'preferred', 'occupied'):
            with self.subTest(mode=mode), socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = 0 if mode == 'ephemeral' else probe.getsockname()[1]
                if mode == 'occupied':
                    probe.listen()
                else:
                    probe.close()
                processes, streams = [], []
                try:
                    for tag, cwd in [('a', target), ('b', target / 'alias' / '..')]:
                        stream = (target / (tag + '.log')).open('wb')
                        streams.append(stream)
                        processes.append(await asyncio.create_subprocess_exec(
                            sys.executable, '-c', child, cwd=cwd,
                            env=dict(os.environ) | {'RACE_TAG': tag, 'RACE_PORT': str(port)},
                            stdin=subprocess.DEVNULL, stdout=stream, stderr=stream))
                    for _ in range(300):
                        if len(list(target.glob('waiting-*'))) == 2:
                            break
                        await asyncio.sleep(.02)
                    self.assertEqual(len(list(target.glob('waiting-*'))), 2)
                    (target / 'go').touch()
                    record_path = self.server.default_identity_file(target)
                    for _ in range(400):
                        if record_path.exists() and any(p.returncode == 0 for p in processes):
                            break
                        await asyncio.sleep(.02)
                    self.assertEqual(len(list(target.glob('worker-*'))), 1,
                                     'Concurrent launch created more than one simulation worker')
                    self.assertEqual(sum(p.returncode is None for p in processes), 1)
                    record = json.loads(record_path.read_text())
                    self.assertEqual(json.loads((target / 'mirror-a.json').read_text()), record)
                    self.assertEqual(json.loads((target / 'mirror-b.json').read_text()), record)
                    async with ClientSession() as client:
                        identity = await (await client.get(record['url'] + 'api/identity')).json()
                        before = await (await client.get(record['url'] + 'api/state')).json()
                        self.assertEqual(identity['project_root'], str(target.resolve()))
                        await asyncio.sleep(.1)
                        after = await (await client.get(record['url'] + 'api/state')).json()
                        self.assertEqual(before['session_id'], after['session_id'])
                        response = await client.post(record['url'] + 'api/shutdown',
                                                     headers={'Origin': record['url'].rstrip('/')})
                        self.assertEqual(response.status, 200)
                    await asyncio.wait_for(asyncio.gather(*(p.wait() for p in processes)), 5)
                    self.assertEqual([p.returncode for p in processes], [0, 0])
                    self.assertFalse(record_path.exists())
                    with socket.socket() as released:
                        released.bind(('127.0.0.1', int(record['url'].split(':')[-1].strip('/'))))
                finally:
                    for process in processes:
                        if process.returncode is None:
                            process.terminate()  # Only the children this test created.
                        await process.wait()
                    for stream in streams:
                        stream.close()
                    for pattern in ('worker-*', 'waiting-*', 'go'):
                        for path in target.glob(pattern):
                            path.unlink()

    async def start(self, port=0):
        task = asyncio.create_task(self.server._serve(port, False, self.identity_file))
        self.tasks.append(task)
        for _ in range(200):
            if task.done():
                await task
            if self.identity_file.exists():
                data = json.loads(self.identity_file.read_text())
                async with ClientSession() as client:
                    try:
                        identity = await (await client.get(data['url'] + 'api/identity')).json()
                        if identity != dict(application_id='neat-car-simulation', protocol=1,
                                            project_root=str(ROOT.resolve())):
                            await asyncio.sleep(.02)
                            continue
                        async with client.get(data['url'] + 'api/state') as response:
                            if response.status == 200:
                                return task, data
                    except OSError:
                        pass
            await asyncio.sleep(.02)
        self.fail('Server did not publish verified readiness')

    async def test_unrelated_listener_on_8765_uses_actual_free_bound_port(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 8765))
            occupied.listen()
            _, data = await self.start(8765)
            self.assertNotEqual(data['url'], 'http://127.0.0.1:8765/')
            self.assertEqual(data['project_root'], str(ROOT.resolve()))
            async with ClientSession() as client:
                response = await client.get(data['url'] + 'api/identity')
                self.assertEqual((await response.json())['project_root'], str(ROOT.resolve()))

    async def test_matching_ready_project_is_reused_without_reset(self):
        owner, data = await self.start()
        origin = data['url'].rstrip('/')
        async with ClientSession() as client:
            before = await (await client.get(data['url'] + 'api/state')).json()
            await client.post(data['url'] + 'api/command', json={'command': 'pause'},
                              headers={'Origin': origin})
            await asyncio.wait_for(self.server._serve(8765, False, self.identity_file), 3)
            after = await (await client.get(data['url'] + 'api/state')).json()
            self.assertEqual(after['session_id'], before['session_id'])
            self.assertTrue(after['paused'])
        self.assertFalse(owner.done())

    async def test_startup_failure_and_crash_release_checkout_lock(self):
        from unittest.mock import patch
        async def never_ready(url, timeout=30):
            return False
        with patch.object(self.server, 'verified_server', side_effect=never_ready):
            with self.assertRaisesRegex(RuntimeError, 'readiness timed out'):
                await self.server._serve(0, False, self.identity_file)
        self.assertFalse(any(t.name == 'simulation-worker' for t in threading.enumerate()))
        self.assertFalse(self.identity_file.exists())
        # A process dying while it owns startup cannot leave a stale PID lock.
        marker = Path(self.folder.name) / 'locked'
        code = ('import asyncio, pathlib, time; from server import StartupLock; '
                'lock=StartupLock(); asyncio.run(lock.acquire()); '
                f'pathlib.Path({str(marker)!r}).touch(); time.sleep(30)')
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', code,
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(200):
                if marker.exists():
                    break
                await asyncio.sleep(.02)
            self.assertTrue(marker.exists())
        finally:
            if process.returncode is None:
                process.terminate()
            await process.wait()
        await asyncio.wait_for(self.start(), 5)

    async def test_cancelled_startup_wait_releases_its_handle(self):
        lock = self.server.StartupLock()
        await lock.acquire()
        task = asyncio.create_task(self.server._serve(0, False, self.identity_file))
        try:
            await asyncio.sleep(.1)
            self.assertFalse(task.done())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            lock.close()
        await asyncio.wait_for(self.start(), 5)

    async def test_stale_identity_is_ignored_and_removed_after_shutdown(self):
        with socket.socket() as stale:
            stale.bind(('127.0.0.1', 0))
            port = stale.getsockname()[1]
        self.identity_file.write_text(json.dumps(dict(application_id='neat-car-simulation', protocol=1,
            project_root=str(ROOT.resolve()), url=f'http://127.0.0.1:{port}/')))
        owner, data = await self.start()
        async with ClientSession() as client:
            response = await client.post(data['url'] + 'api/shutdown',
                                         headers={'Origin': data['url'].rstrip('/')})
            self.assertEqual(response.status, 200)
        await asyncio.wait_for(owner, 3)
        self.assertFalse(self.identity_file.exists())
        _, relaunched = await self.start()
        self.assertTrue(relaunched['url'].startswith('http://127.0.0.1:'))

    async def fake_server(self, identity, ready=True):
        app = web.Application()
        async def get_identity(request):
            return web.json_response(identity)
        async def get_state(request):
            return web.json_response({'schema_version': 1}, status=200 if ready else 503)
        app.add_routes([web.get('/api/identity', get_identity), web.get('/api/state', get_state)])
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return str(client.make_url('/'))

    async def test_wrong_checkout_application_and_protocol_are_not_reused(self):
        for changed in ({'project_root': str(Path(self.folder.name).resolve())},
                        {'application_id': 'another-app'}, {'protocol': 2}):
            with self.subTest(changed=changed):
                identity = dict(application_id='neat-car-simulation', protocol=1,
                                project_root=str(ROOT.resolve())) | changed
                url = await self.fake_server(identity)
                # A plausible file is insufficient: verify the actual endpoint.
                self.identity_file.write_text(json.dumps(dict(application_id='neat-car-simulation',
                    protocol=1, project_root=str(ROOT.resolve()), url=url)))
                owner, data = await self.start()
                self.assertNotEqual(data['url'], url)
                owner.cancel()
                await asyncio.gather(owner, return_exceptions=True)

    async def test_matching_identity_is_not_ready_until_state_succeeds(self):
        identity = dict(application_id='neat-car-simulation', protocol=1,
                        project_root=str(ROOT.resolve()))
        url = await self.fake_server(identity, ready=False)
        self.assertFalse(await self.server.verified_server(url, timeout=.15))

    async def test_identity_path_is_keyed_by_canonical_project_root(self):
        first = self.server.default_identity_file(ROOT)
        self.assertEqual(first, self.server.default_identity_file(ROOT / 'web' / '..'))
        self.assertNotEqual(first.name, self.server.default_identity_file(Path(self.folder.name)).name)

    @unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh.exe'),
                         'Directory junction regression needs Windows and PowerShell 7 cleanup')
    async def test_powershell_launch_through_junction_uses_canonical_identity_and_reuses_session(self):
        target = Path(self.folder.name) / 'actual checkout'
        alias = Path(self.folder.name) / 'junction route'
        target.mkdir()
        for source in ROOT.glob('*.py'):
            shutil.copy2(source, target)
        for directory in ('scripts', 'assets', 'demos'):
            shutil.copytree(ROOT / directory, target / directory)
        interpreter = target / '.venv'
        junctions = []
        powershell = shutil.which('powershell.exe')
        self.assertIsNotNone(powershell)
        junction_shell = shutil.which('pwsh.exe')
        self.assertIsNotNone(junction_shell, 'PowerShell 7 is required for safe junction cleanup')

        async def shell(arguments, environment=None, executable=None):
            output = target / f'launcher-check-{time.time_ns()}.log'
            with output.open('wb') as stream:
                process = await asyncio.create_subprocess_exec(
                    executable or powershell, '-NoProfile', '-ExecutionPolicy', 'Bypass', *arguments,
                    stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                    env=environment if environment is not None else dict(os.environ))
                code = await asyncio.wait_for(process.wait(), 15)
            return code, output.read_text(encoding='utf-8', errors='replace')

        try:
            for link, destination in ((interpreter, Path(sys.prefix)), (alias, target)):
                environment = os.environ | {'JUNCTION_TEST_ALIAS': str(link),
                                            'JUNCTION_TEST_TARGET': str(destination)}
                code, output = await shell(['-Command',
                    'New-Item -ItemType Junction -Path $env:JUNCTION_TEST_ALIAS '
                    '-Target $env:JUNCTION_TEST_TARGET | Out-Null'], environment)
                self.assertEqual(code, 0, output)
                junctions.append((link, destination.resolve()))
                self.assertEqual(link.resolve(), destination.resolve())
            arguments = ['-File', str(alias / 'scripts' / 'launch.ps1'), '-NoBrowser',
                         '-Port', '0', '-StartupTimeoutSeconds', '5']
            direct = ['-File', str(target / 'scripts' / 'launch.ps1'), '-NoBrowser',
                      '-Port', '0', '-StartupTimeoutSeconds', '10']
            simultaneous = await asyncio.gather(shell(arguments), shell(direct))
            for code, output in simultaneous:
                self.assertEqual(code, 0, output)
            self.assertEqual(simultaneous[0][1].strip(), simultaneous[1][1].strip())
            record = json.loads(next((target / 'logs').glob('server-*.json')).read_text())
            self.assertEqual(record['project_root'], str(target.resolve()))
            self.assertNotEqual(record['project_root'], str(alias))
            async with ClientSession() as client:
                before = await (await client.get(record['url'] + 'api/state')).json()
                code, output = await shell(arguments)
                self.assertEqual(code, 0, output)
                after = await (await client.get(record['url'] + 'api/state')).json()
            self.assertEqual(after['session_id'], before['session_id'])
            self.assertEqual(json.loads(next((target / 'logs').glob('server-*.json')).read_text())['url'],
                             record['url'])
        finally:
            # Stop a listener even when the old launcher rejects its canonical identity.
            for path in (target / 'logs').glob('server-*.json'):
                record = json.loads(path.read_text())
                async with ClientSession() as client:
                    try:
                        await client.post(record['url'] + 'api/shutdown',
                                          headers={'Origin': record['url'].rstrip('/')})
                    except OSError:
                        pass
            for _ in range(100):
                if not list((target / 'logs').glob('server-*.json')):
                    break
                await asyncio.sleep(.02)
            # Remove only the checked junction entries, never recurse into their targets.
            for link, destination in reversed(junctions):
                self.assertEqual(link.resolve(), destination)
                environment = os.environ | {'JUNCTION_TEST_ALIAS': str(link)}
                code, output = await shell(['-Command',
                    'Remove-Item -LiteralPath $env:JUNCTION_TEST_ALIAS -Force'], environment, junction_shell)
                self.assertEqual(code, 0, output)

    async def test_browser_opens_once_only_after_ready(self):
        from unittest.mock import patch
        opened = []
        with patch.object(self.server.webbrowser, 'open', side_effect=opened.append):
            task = asyncio.create_task(self.server._serve(0, True, self.identity_file))
            self.tasks.append(task)
            for _ in range(200):
                if opened:
                    break
                await asyncio.sleep(.02)
            self.assertEqual(len(opened), 1)
            async with ClientSession() as client:
                self.assertEqual((await client.get(opened[0] + 'api/state')).status, 200)
            await self.server._serve(8765, True, self.identity_file)
            self.assertEqual(opened, [opened[0], opened[0]])
