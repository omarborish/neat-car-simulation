"""Loopback HTTP transport with one owner for all simulation work."""
import asyncio
import argparse
from collections import deque
from concurrent.futures import Future
import ipaddress
import hashlib
import json
import logging
import errno
import os
from pathlib import Path
import queue
import socket
import threading
import time
from urllib.parse import urlsplit
import webbrowser

from aiohttp import ClientSession, ClientTimeout, ClientError, web, WSCloseCode

from circuits import circuit_catalog
from runtime import Runtime
from tracks import ROOT, TRACKS, load_track

MAX_MESSAGE = 32 * 1024
MAX_CATALOG = 256 * 1024
QUEUE_LIMIT = 50
STREAM_INTERVAL = .05
SEND_TIMEOUT = 1
WEB_FILES = frozenset(('index.html', 'app.js', 'styles.css', 'renderer.js', 'preferences.js'))
ASSET_FILES = frozenset(['tracks/' + spec.filename for spec in TRACKS] +
                        ['cars/car.png'] + ['cars/car' + color + '.png' for color in
                                            ('red', 'green', 'blue', 'yellow', 'orange', 'pink', 'purple')])


def _encode(data, limit=MAX_MESSAGE):
    encoded = json.dumps(data, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if len(encoded) > limit:
        raise ValueError('Published message exceeds the transport limit')
    return encoded


def _rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    return value


class CommandQueueFull(Exception):
    pass


class SimulationService:
    """HTTP reads immutable JSON bytes; only this thread touches Runtime."""
    def __init__(self, source):
        self.source = source
        self.commands = queue.Queue(maxsize=QUEUE_LIMIT)
        self.queue_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self._run, name='simulation-worker')
        self.latest = None
        self.catalog = None
        self.catalog_width = None
        self.error = None
        self.sockets = set()
        self.steps = deque()
        self.measuring_since = time.monotonic()

    def submit(self, data):
        future = Future()
        with self.queue_lock:
            if self.stop_event.is_set() or self.error:
                raise RuntimeError(self.error or 'Simulation is stopping')
            try:
                self.commands.put_nowait((data, future))
            except queue.Full:
                raise CommandQueueFull('Command queue is full; try again shortly') from None
        return future

    def _project(self, snapshot):
        # All cars retain poses/statistics. Only the leader carries sensor detail.
        snapshot['cars'] = [_rounded({key: value for key, value in car.items()
                                      if key not in ('sensors', 'inputs', 'action')})
                            for car in snapshot['cars']]
        snapshot['leader'] = _rounded(snapshot['leader'])
        now = time.monotonic()
        while self.steps and self.steps[0] < now - 1:
            self.steps.popleft()
        snapshot['effective_step_rate'] = (0 if snapshot['paused'] else
                                          round(len(self.steps) / min(1, max(.001, now - self.measuring_since)), 2))
        return snapshot

    def _publish(self, snapshot):
        if snapshot['paused']:
            self.steps.clear()
            self.measuring_since = time.monotonic()
        encoded_snapshot = _encode(self._project(snapshot))
        width = snapshot['settings']['road_width']
        if width != self.catalog_width:
            tracks = [dict(id=spec.id, name=spec.name, kind='bitmap', group='Original circuits',
                           image='/assets/tracks/' + spec.filename, start=list(spec.start), angle=spec.angle,
                           geometry_revision='bitmap-1', reward_version='distance-1', geometry=None)
                      for spec in TRACKS]
            for item in circuit_catalog():
                track = load_track(item['id'], width)
                tracks.append(item | dict(kind='vector', geometry=track.geometry,
                                           start=list(track.start), angle=track.angle))
            self.catalog = _encode(dict(schema_version=1, world=[1920, 1080], road_width=width,
                                        tracks=tracks), MAX_CATALOG)
            self.catalog_width = width
        self.latest = encoded_snapshot

    def _run(self):
        active = None
        try:
            runtime = self.source() if callable(self.source) else self.source
            self.measuring_since = time.monotonic()
            self._publish(runtime.snapshot())
            deadline = time.monotonic() + 1 / runtime.step_rate
            next_publish = deadline + STREAM_INTERVAL
            while not self.stop_event.is_set():
                try:
                    active = self.commands.get(timeout=max(0, min(.02, deadline - time.monotonic())))
                except queue.Empty:
                    active = None
                if active:
                    data, future = active
                    if future.set_running_or_notify_cancel():
                        result = runtime.command(data)
                        if not result['ok']:
                            result['error'] = result['error'][:1000]
                        self._publish(result['snapshot'])
                        result['snapshot'] = json.loads(self.latest)
                        encoded = _encode(result)
                        if not future.done():
                            future.set_result(encoded)
                    active = None
                    # A costly command must not leave old timing debt.
                    deadline = time.monotonic() + 1 / runtime.step_rate
                    next_publish = deadline + STREAM_INTERVAL
                now = time.monotonic()
                if runtime.paused:
                    deadline = now + .02
                else:
                    interval = 1 / runtime.step_rate
                    count = 0
                    while now >= deadline and count < 5 and not self.stop_event.is_set():
                        runtime.step()
                        self.steps.append(time.monotonic())
                        # Give the HTTP loop a scheduling opportunity even when
                        # a large population cannot keep up with the target.
                        time.sleep(0)
                        deadline += interval
                        count += 1
                        now = time.monotonic()
                    if now >= deadline:
                        deadline = now + interval
                if now >= next_publish:
                    self._publish(runtime.snapshot())
                    next_publish = time.monotonic() + STREAM_INTERVAL
        except Exception as error:
            self.error = 'Simulation worker failed: ' + str(error)
        finally:
            with self.queue_lock:
                self.stop_event.set()
                if active and not active[1].done():
                    active[1].set_exception(RuntimeError(self.error or 'Simulation stopped'))
                while True:
                    try:
                        _, future = self.commands.get_nowait()
                    except queue.Empty:
                        break
                    if not future.done():
                        future.set_exception(RuntimeError(self.error or 'Simulation stopped'))

    async def stop(self):
        self.stop_event.set()
        await asyncio.gather(*(ws.close(code=WSCloseCode.GOING_AWAY, message=b'Simulation stopped')
                               for ws in tuple(self.sockets)), return_exceptions=True)
        if self.worker.ident is not None:
            await asyncio.to_thread(self.worker.join)


SERVICE_KEY = web.AppKey('simulation_service', SimulationService)
SHUTDOWN_KEY = web.AppKey('shutdown_event', asyncio.Event)


def _authority(value):
    try:
        parsed = urlsplit('http://' + value)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError
        hostname = parsed.hostname
        if hostname != 'localhost' and not ipaddress.ip_address(hostname).is_loopback:
            raise ValueError
        return hostname, parsed.port or 80
    except (ValueError, TypeError):
        raise web.HTTPForbidden(text='Use a loopback Host') from None


@web.middleware
async def local_requests(request, handler):
    authority = _authority(request.host)
    if request.method not in ('GET', 'HEAD') or request.path == '/ws':
        origin = request.headers.get('Origin', '')
        try:
            parsed = urlsplit(origin)
        except ValueError:
            raise web.HTTPForbidden(text='Provide a valid local Origin') from None
        if (parsed.scheme != request.scheme or not parsed.netloc or parsed.path or parsed.query or parsed.fragment
                or _authority(parsed.netloc) != authority
                or request.headers.get('Sec-Fetch-Site') == 'cross-site'):
            raise web.HTTPForbidden(text='State-changing requests require the same local Origin')
    response = await handler(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def _json_response(body, status=200):
    return web.Response(body=body, status=status, content_type='application/json')


def project_identity():
    return dict(application_id='neat-car-simulation', protocol=1, project_root=str(ROOT.resolve()))


async def identity(request):
    return web.json_response(project_identity())


async def state(request):
    service = request.app[SERVICE_KEY]
    if service.latest is None or service.error or service.stop_event.is_set():
        return web.json_response(dict(ok=False, error=service.error or 'Simulation is starting or stopping'), status=503)
    return _json_response(service.latest)


async def catalog(request):
    service = request.app[SERVICE_KEY]
    if service.catalog is None:
        return web.json_response(dict(ok=False, error=service.error or 'Track catalog is starting'), status=503)
    return _json_response(service.catalog)


async def command(request):
    try:
        def reject_constant(value):
            raise ValueError('Nonfinite JSON')
        data = await request.json(loads=lambda text: json.loads(text, parse_constant=reject_constant))
        if not isinstance(data, dict) or not isinstance(data.get('command'), str):
            raise ValueError('Provide an object with a command name')
    except (ValueError, UnicodeError, RecursionError):
        return web.json_response(dict(ok=False, error='Provide a valid JSON command object'), status=400)
    try:
        future = request.app[SERVICE_KEY].submit(data)
        body = await asyncio.wrap_future(future)
    except CommandQueueFull as error:
        return web.json_response(dict(ok=False, error=str(error)), status=429)
    except RuntimeError as error:
        return web.json_response(dict(ok=False, error=str(error)), status=503)
    return _json_response(body, 200 if json.loads(body)['ok'] else 400)


async def shutdown(request):
    # Read even an unused body so the same inbound size limit applies here.
    await request.read()
    request.app[SHUTDOWN_KEY].set()
    return web.json_response(dict(ok=True))


async def websocket(request):
    service = request.app[SERVICE_KEY]
    if service.stop_event.is_set():
        raise web.HTTPServiceUnavailable(text='Simulation is stopping')
    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE, heartbeat=20, writer_limit=MAX_MESSAGE, timeout=1)
    await ws.prepare(request)
    service.sockets.add(ws)

    async def send_latest():
        while not ws.closed and not service.stop_event.is_set():
            if service.latest is not None:
                await asyncio.wait_for(ws.send_str(service.latest.decode('utf-8')), SEND_TIMEOUT)
            await asyncio.sleep(STREAM_INTERVAL)

    sender = asyncio.create_task(send_latest())
    # A failed/slow writer wakes the handler's sole reader via socket closure.
    async def watch_sender():
        try:
            await sender
        except (asyncio.TimeoutError, OSError, RuntimeError):
            pass
        await ws.close(code=WSCloseCode.GOING_AWAY, message=b'Snapshot stream disconnected')

    watcher = asyncio.create_task(watch_sender())
    try:
        async for message in ws:
            if message.type in (web.WSMsgType.TEXT, web.WSMsgType.BINARY):
                await ws.close(code=WSCloseCode.POLICY_VIOLATION, message=b'Use POST /api/command')
                break
    finally:
        service.sockets.discard(ws)
        sender.cancel()
        watcher.cancel()
        await asyncio.gather(sender, watcher, return_exceptions=True)
    return ws


def _allowed_file(directory, name, allowed):
    if name not in allowed or '\\' in name:
        raise web.HTTPNotFound()
    base = (ROOT / directory).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


async def index(request):
    if (ROOT / 'web' / 'index.html').is_file():
        return _allowed_file('web', 'index.html', WEB_FILES)
    return web.Response(text='<!doctype html><html><title>NEAT Car Simulation</title><body><h1>NEAT Car Simulation</h1><p>The local simulation server is running. The browser controls will be available when the interface is installed.</p></body></html>', content_type='text/html')


async def web_file(request):
    return _allowed_file('web', request.match_info['file'], WEB_FILES)


async def asset(request):
    return _allowed_file('assets', request.match_info['allowed_path'], ASSET_FILES)


def create_app(runtime: Runtime = None, shutdown_event=None) -> web.Application:
    """Transfer ownership of a Runtime, or construct the default on the worker.

    A zero-argument factory is accepted for integrations needing their own save
    directory. Never read or mutate a supplied Runtime after transferring it.
    """
    app = web.Application(client_max_size=MAX_MESSAGE, middlewares=[local_requests])
    service = SimulationService(runtime if runtime is not None else lambda: Runtime(ROOT / 'saved'))
    app[SERVICE_KEY] = service
    app[SHUTDOWN_KEY] = shutdown_event if shutdown_event is not None else asyncio.Event()

    async def lifecycle(application):
        service.worker.start()
        async def watch_shutdown():
            await application[SHUTDOWN_KEY].wait()
            await service.stop()
        watcher = asyncio.create_task(watch_shutdown())
        try:
            yield
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            await service.stop()

    app.cleanup_ctx.append(lifecycle)
    app.add_routes([web.get('/', index), web.get('/web/{file}', web_file),
                    web.get('/assets/{allowed_path:.*}', asset), web.get('/api/identity', identity),
                    web.get('/api/catalog', catalog), web.get('/api/state', state),
                    web.get('/ws', websocket), web.post('/api/command', command),
                    web.post('/api/shutdown', shutdown)])
    return app


def default_identity_file(root=ROOT):
    root = Path(root).resolve()
    key = hashlib.sha256(os.path.normcase(str(root)).encode('utf-8')).hexdigest()[:16]
    return root / 'logs' / f'server-{key}.json'


def _local_url(url):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                and parsed.port and not parsed.username and not parsed.password
                and parsed.path == '/' and not parsed.query and not parsed.fragment)
    except (TypeError, ValueError):
        return False


async def verified_server(url, timeout=30):
    """Accept only this checkout's identity and a successful state response."""
    if not _local_url(url):
        return False
    deadline = time.monotonic() + timeout
    async with ClientSession(timeout=ClientTimeout(total=min(1, timeout)), trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                async with client.get(url + 'api/identity', allow_redirects=False) as response:
                    if response.status != 200 or response.content_length and response.content_length > MAX_MESSAGE:
                        return False
                    body = await response.content.read(MAX_MESSAGE + 1)
                    if len(body) > MAX_MESSAGE or json.loads(body) != project_identity():
                        return False
                async with client.get(url + 'api/state', allow_redirects=False) as response:
                    if response.status == 200:
                        return True
                    if response.status != 503:
                        return False
            except (ClientError, OSError, asyncio.TimeoutError, ValueError):
                return False
            await asyncio.sleep(.1)
    return False


def _read_identity(path):
    try:
        if path.stat().st_size > MAX_MESSAGE:
            return None
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and all(data.get(key) == value for key, value in project_identity().items()):
            return data
    except (OSError, ValueError):
        pass
    return None


class StartupLock:
    """OS-owned checkout lock; a crashed process releases it automatically.

    Never unlink the file: replacing a locked inode would split POSIX owners.
    Nonblocking attempts keep the event loop and cancellation responsive.
    """
    def __init__(self):
        path = default_identity_file().with_suffix('.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        if path.stat().st_size == 0:
            self.stream.write(b'\0')
            self.stream.flush()
        self.owned = False

    async def acquire(self):
        while not self.owned:
            try:
                self.stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.owned = True
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                await asyncio.sleep(.05)

    def close(self):
        # Closing releases both Windows byte-range locks and POSIX flock.
        self.stream.close()


def _write_identity(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(record), encoding='utf-8')
    temporary.replace(path)


async def _serve(port, open_browser, identity_file=None):
    canonical = default_identity_file()
    identity_file = Path(identity_file).resolve() if identity_file is not None else canonical
    records = list(dict.fromkeys((canonical, identity_file)))
    ownership = StartupLock()
    try:
        await ownership.acquire()
        await _serve_owned(port, open_browser, records, ownership)
    finally:
        ownership.close()


async def _serve_owned(port, open_browser, records, ownership):
    # Re-read only after ownership, including when callers supplied different
    # identity mirrors. Canonical aliases always discover the same winner.
    candidates = []
    for path in records:
        previous = _read_identity(path)
        if previous and isinstance(previous.get('url'), str):
            candidates.append(previous['url'])
    if port:
        candidates.append(f'http://127.0.0.1:{port}/')
    for url in dict.fromkeys(candidates):
        if await verified_server(url):
            # A lost/stale identity file can recover a matching default listener.
            for path in records:
                _write_identity(path, project_identity() | {'url': url})
            if open_browser:
                webbrowser.open(url)
            return

    # Bind and retain the socket before choosing the URL; never probe then release.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    runner = None
    record = None
    try:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
            listener.bind(('127.0.0.1', 0))
        listener.listen(socket.SOMAXCONN)
        listener.setblocking(False)
        url = f'http://127.0.0.1:{listener.getsockname()[1]}/'
        event = asyncio.Event()
        app = create_app(shutdown_event=event)
        runner = web.AppRunner(app, shutdown_timeout=2, handler_cancellation=True, access_log=None)
        await runner.setup()
        site = web.SockSite(runner, listener)
        await site.start()
        record = project_identity() | {'url': url}
        if not await verified_server(url):
            raise RuntimeError(app[SERVICE_KEY].error or
                               'Simulation readiness timed out; inspect logs/launch-error-*.log')
        for path in records:
            _write_identity(path, record)
        ownership.close()  # Publish verified readiness before admitting a contender.
        logging.info('Simulation ready: %s', url)
        if open_browser:
            webbrowser.open(url)
        await event.wait()
    finally:
        if runner is not None:
            await runner.cleanup()
        listener.close()
        for path in records:
            if record and _read_identity(path) == record:
                path.unlink(missing_ok=True)


def serve(port=8765, open_browser=True, identity_file=None) -> None:
    """Reuse this ready checkout, or run until Stop; cleanup releases its listener."""
    try:
        asyncio.run(_serve(port, open_browser, identity_file))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    parser = argparse.ArgumentParser(description='Run the local browser simulation.')
    parser.add_argument('--port', type=int, default=8765, help='Preferred port; occupied ports fall back automatically.')
    parser.add_argument('--no-browser', action='store_true', help='Leave browser opening to the launcher.')
    parser.add_argument('--identity-file', type=Path, help='Runtime identity path (default: project-keyed file in logs).')
    arguments = parser.parse_args()
    if not 0 <= arguments.port <= 65535:
        parser.error('--port must be between 0 and 65535')
    serve(arguments.port, not arguments.no_browser, arguments.identity_file)
