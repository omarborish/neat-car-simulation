# Browser Simulation Implementation Plan

Status: approved plan implemented on `feature/browser-demo`, October 12, 2026;
final review and publication remain release gates. The original task text and
unchecked checklists below are retained as the historical implementation plan,
not a current progress tracker. See README.md and docs/VERIFICATION.md for the
implemented behavior, test evidence, and explicit verification limits.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Launch Omar's existing NEAT driving experiment in a polished local browser, with Advanced controls and editable circuit approximations.

**Architecture:** Keep Python as the authority for driving and evolution. A local aiohttp server streams snapshots from one simulation worker to a Canvas interface. Track geometry, experiment settings, and saved-driver compatibility have explicit versioned boundaries.

**Tech Stack:** Python 3.10–3.13, pygame 2.6.1, neat-python 0.92, aiohttp, browser HTML/CSS/ES modules, unittest. No Node installation or frontend build step is required for the user.

**Spec:** `docs/superpowers/specs/2026-10-10-browser-simulation-design.md` (approved by Omar).

## Global Constraints

- Keep five sensors and four outputs.
- Population size (10–100); episode limit (300–3,600 steps).
- Original tracks retain their current distance fitness to preserve the bundled driver.
- Omar will select actual F1 car images later.
- Bind the service to loopback. No online service is needed to train or replay.
- Advanced is collapsed initially. Applying driving/training changes explicitly starts a new experiment.
- This stays a flat sensor-based NEAT experiment.
- Update the existing `omarborish/neat-car-simulation` repository and refreshed download ZIP after verification.

## Review Focus

1. A user edits Advanced fields without applying them: the active session continues unchanged (Task 5).
2. A narrow or malformed circuit places the spawn against a boundary: reject the preset with a useful error (Task 2).
3. The page reloads or disconnects during training: reconnect to the existing session without reseeding it (Tasks 4–5).
4. A custom-settings champion exists next to the bundled demo: choose a compatible driver without overwriting or silently substituting an incompatible one (Tasks 1 and 3).
5. A second launcher runs while another application owns the preferred port: verify server identity before reuse, otherwise choose a free port (Task 6).

## File responsibilities

- `settings.py`: immutable validated experiment settings and fingerprints.
- `circuits.py`, `assets/circuits/monza.json`, `assets/circuits/silverstone.json`: geometry loading, sampling, road masks, gates, and reference metadata.
- `progress.py`: ordered forward checkpoint/lap accounting.
- `simulator.py`, `tracks.py`, `training.py`, `models.py`: extend existing interfaces with optional settings while preserving legacy callers.
- `runtime.py`: the one live browser session, replay choice, commands, and snapshots.
- `server.py`: loopback HTTP/WebSocket transport, worker lifecycle, port selection, and browser launch.
- `web/index.html`, `web/style.css`, `web/app.js`, `web/renderer.js`, `web/preferences.js`: browser controls, graphics, and visual preferences.
- `scripts/python.ps1`, `scripts/launch.ps1`, `scripts/setup.ps1`, `requirements.txt`: dependency detection and browser launch.
- `tests/test_settings.py`, `tests/test_circuits.py`, `tests/test_progress.py`, `tests/test_runtime.py`, `tests/test_server.py`: behavioral checks alongside the existing tests.
- `README.md`, `ATTRIBUTION.md`, `docs/INTERVIEW.md`, `docs/browser-*.png`: accurate user guidance and screenshots.

## Task 1: Settings and driver compatibility

**Files:** Create `settings.py`, `tests/test_settings.py`; modify `simulator.py`, `models.py`, `tests/test_models.py`.

**Interfaces:** `ExperimentSettings.from_dict(data: dict) -> ExperimentSettings`; `settings.to_dict() -> dict`; `settings.fingerprint(track_id: str, geometry_revision: str, reward_version: str) -> str`. Extend `Car(track, color="red", settings=None)` and `save_driver(..., experiment=None)` with optional parameters. `Driver.experiment` is either validated metadata or `None` for legacy files.

- [ ] Write failing tests: defaults give max speed 18, steering step 5, sensor range 300, population 30, seed 7, episode steps 1,200, and vector road width 120. Reject booleans, non-finite numbers, unknown keys, population 9/101, and episode limits 299/3,601. Changing a visual color does not affect the fingerprint; changing a physics value does. Legacy driver loading still gives identical actions.
- [ ] Run `.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_settings.py -v`; expect missing settings implementation, not an unrelated import error. Run new model tests and observe their intended failures.
- [ ] Implement settings: max speed 6–24, steering step 1–10 degrees, sensor range 100–600, seed 0–2,147,483,647, road width 90–180. Use canonical sorted JSON and SHA-256 for fingerprints. Keep initial speed 10 and minimum speed 6; clamp initial speed to the chosen maximum. Preserve original action, sensor, and collision results with default settings.
- [ ] Add saved format 2 containing validated experiment settings, geometry revision, reward version, and fingerprint. Retain format 1 support under original physics defaults. Never interpret arbitrary file content as executable Python. Preserve existing numeric/topology checks.
- [ ] Run settings/model tests and existing bundled-demo test; expect PASS and Classic fitness approximately 359.5 after 1,200 steps. Commit this task.

## Task 2: Circuit geometry and ordered progress

**Files:** Create `circuits.py`, `progress.py`, two circuit JSON files, `tests/test_circuits.py`, `tests/test_progress.py`; modify `tracks.py`, `simulator.py`.

**Interfaces:** `load_circuit(track_id: str, road_width: float) -> Track`; `circuit_catalog() -> list[dict]`; `CheckpointProgress(gates: list, road_width: float)` with `update(previous: tuple, current: tuple) -> None`, `laps`, `fitness`, and `steps_since_progress`. Track adds optional `geometry`, `geometry_revision`, and `reward_version` fields. `load_track(track_id, road_width=120)` resolves bitmap or vector tracks.

- [ ] Write failing tests for closed/finite geometry, safe spawn at widths 90/120/180, rejection of disconnected/self-intersecting roads or malformed points, and decoration-independent collision. A synthetic loop must count one lap only after all gates in forward order; reverse crossing, crossing the finish first, repeated gate crossing, and circling between two gates earn no extra lap.
- [ ] Run circuit/progress test files; expect the intended missing implementations.
- [ ] Consult the official circuit diagrams linked in the spec. Author normalized, original GP-layout centerlines with sufficient points to preserve chicanes and sweeping corners. Record reference length/turns separately from schematic geometry, revision `1`, direction, turn labels, and three sector boundaries. Bahrain remains the explicitly later candidate.
- [ ] Sample the centerline into a 1,920 × 1,080 world preserving aspect ratio; use the sampled points for both the road mask and browser asphalt. Generate spawn heading from the initial segment. Validate footprint clearance, road continuity, and non-adjacent road overlap for each supported width; exclude invalid geometry/presets rather than silently merging neighboring roads.
- [ ] Implement gate crossings using segment intersection with finite gates and positive motion along the local forward tangent. Reward 100 per newly accepted ordered gate, with forward progress to the next gate capped below 100; lap completion requires the whole gate sequence. Stop cars after 600 steps without an accepted gate. Use reward version `checkpoints-1`; leave bitmap fitness unchanged.
- [ ] Run geometry/progress and original simulator tests; expect PASS. Visually inspect both schematic outlines against references before accepting them. Commit this task.

## Task 3: Browser session controller

**Files:** Create `runtime.py`, `tests/test_runtime.py`; modify `training.py`, `models.py`.

**Interfaces:** `Runtime(save_dir: Path)`; `runtime.command(data: dict) -> dict`; `runtime.step() -> None`; `runtime.snapshot() -> dict`. Session accepts `settings=None` and uses its population/episode parameters. Snapshot schema version 1 contains session ID, episode ID, mode, paused, track ID, settings, generation, population, alive, fitness, cars, leader sensors/action, laps, replay provenance, and effective step rate.

- [ ] Write failing tests: initial Classic replay moves; pause freezes position; color changes preserve generation/position; restart with the same seed reproduces early training; changing settings creates a new session ID; unknown commands leave the current session intact. Custom training saves cannot replace `demos/classic.json` or legacy `saved/classic.json`.
- [ ] Run runtime tests and observe intended failures.
- [ ] Implement commands `pause`, `resume`, `restart`, `start`, `appearance`, and `apply_settings`. Default to active Classic replay. New tracks start in Train unless a compatible champion exists. Permit a Classic driver on another track only through an explicit transfer-test command with compatible physics; expose training track and transfer status.
- [ ] Preserve `Session(track_id, color, seed, save_dir)` legacy behavior. Browser runs save under `saved/experiments/<fingerprint>/<track>.json`; write format 2 and check compatibility before comparing saved fitness. New circuits use checkpoint fitness. Replay loops create a new episode ID to prevent interpolating across a reset.
- [ ] Run runtime, training, model, and bundled-demo tests. Complete one genuine NEAT generation on Monza and Silverstone and replay any produced champion; success means valid evaluation and saving, not a claimed successful lap. Commit this task.

## Task 4: Local transport and worker lifecycle

**Files:** Create `server.py`, `tests/test_server.py`; modify `requirements.txt`.

**Interfaces:** `create_app(runtime: Runtime, shutdown_event=None) -> aiohttp.web.Application`; `serve(port=8765, open_browser=True) -> None`. Routes: `GET /`, `/web/{file}`, `/assets/{allowed_path}`, `/api/identity`, `/api/catalog`, `/api/state`, `/ws`; `POST /api/command`, `/api/shutdown`. Identity includes application ID `neat-car-simulation`, protocol 1, and canonical project-root identifier.

- [ ] Write failing aiohttp integration tests for identity/state, WebSocket snapshots, validated commands, reconnect preserving the session, malformed/oversized requests, unknown asset paths, and shutdown cleanup. A slow/disconnected client cannot stall training.
- [ ] Resolve and pin a current compatible non-prerelease aiohttp version whose Python requirement includes 3.10; verify it against official package metadata, install into the project environment, then run integration tests and observe the intended missing server behavior.
- [ ] Use a single simulation worker with a bounded command queue and immutable latest snapshot. All Session/NEAT mutation stays on that worker. HTTP remains responsive during generation creation. Stream snapshots at up to 20 Hz without retaining per-client backlogs; bound messages to 32 KiB and commands to 50 queued requests.
- [ ] Target 60 fixed steps per second at 1× and 240 at 4×. Bound catch-up to five steps and discard excess timing backlog; report measured effective rate. Validate loopback Host and same-origin state-changing requests, allow only explicit asset directories, and reject path traversal. Stop closes sockets, terminates the worker, and releases the port.
- [ ] Run integration/runtime tests; expect PASS with real streamed positions. Commit this task.

## Task 5: Canvas interface and Advanced controls

**Files:** Create the five `web/` files; extend catalog/snapshot fields only where required by these defined interfaces.

**Interfaces:** `renderer.draw(snapshot, previousSnapshot, appearance, camera)`; `preferences.load()` and `preferences.save(appearance)` store visual settings only. `app.js` owns connection/reconnect, drafts, commands, and effective control values. The server remains authoritative.

- [ ] Define visual tokens: panel `#202A35`, page `#151C24`, text `#EEF2F5`, muted `#A8B4C1`, accent `#70B3D7`, track surroundings `#526D5B`. Use Segoe UI for controls and tabular numerals for timing values. Choose a large track viewport with a compact control rail and a single information strip; no repeated statistic cards. Review these choices against the approved motorsport brief before building.
- [ ] Implement local Canvas rendering with device-pixel-ratio scaling, sprite rotation, sampled vector roads, kerbs, and overlays. Use fit/zoom/follow camera transforms consistently for the road, cars, and sensors. Interpolate only snapshots sharing a session/episode ID. Reduced-motion preference disables interpolation and trails.
- [ ] Add track previews grouped into Circuit studies and Original tracks; color controls; Replay/Train; pause/restart; speed; fullscreen; presentation mode; sensor inspector; visible connection status; Stop server. Label untrained circuits and transfer tests honestly. Keep actual F1 car asset selection deferred.
- [ ] Add collapsed Advanced appearance/driving/training groups with draft values, explicit Apply and restart, and Reset defaults. Applied values update only after server acknowledgement. Store visual preferences safely; unavailable or malformed browser storage falls back to defaults. Show simulation units and explain compatibility errors with a restore-compatible-preset action.
- [ ] Verify in the real browser: resize/fullscreen keeps cars aligned; zoom/follow stays coherent; controls work by keyboard; text entry does not fire shortcuts; draft edits do not restart training; reload reconnects to the same session; malformed preferences do not break startup; offline operation has no remote font/asset requests. Save actual browser screenshots and inspect readability at 1,280 × 800 and a narrow viewport. Commit this task.

## Task 6: One-click browser launch

**Files:** Modify `scripts/python.ps1`, `scripts/launch.ps1`, `scripts/setup.ps1`; preserve `Launch.bat` and `Setup.bat` entry points. Add launch cases to `tests/test_server.py`.

**Interfaces:** `server.py` CLI supports `--port`, `--no-browser`, and `--identity-file`. Runtime identity stores the actual bound URL under `logs/`, keyed by the project root. Native `app.py` remains available as a documented fallback.

- [ ] Write failing tests using actual occupied sockets: unrelated service on 8765 chooses a free port; verified matching project server is reused; stale identity is ignored; a different checkout is not mistaken for this project. Observe intended failures.
- [ ] Update Python dependency detection to require the pinned aiohttp alongside the existing libraries. Setup installs requirements and reports the correct library count. Launch starts the server with a hidden helper window, waits for verified readiness with a bounded timeout, then opens the browser once. Failed readiness points to useful logs.
- [ ] Verify double-click launch from a folder with spaces, a second launch, shutdown followed by relaunch, and missing dependencies. Confirm no separate simulation window appears. Run server tests; expect PASS. Commit this task.

## Task 7: Final validation, documentation, and publication

**Files:** Update README, attribution, interview notes, browser screenshots, and the output ZIP; retain tutorial and AI assistance disclosures.

- [ ] Run the full unittest suite with dummy SDL for headless simulation checks; expect all existing and new checks to pass. Reconfirm Classic's 1,200-step survival/coverage and one completed generation on both circuit studies.
- [ ] Review the whole change with fresh context, emphasizing the Review Focus conditions and the approved spec. Resolve material findings, rerun affected checks, and record any remaining limitations accurately.
- [ ] Demonstrate actual browser launch, saved replay, live training, track/color changes, Advanced apply/reset, disconnect/reconnect, and shutdown on Omar's machine. Record effective rendering/simulation rates observed instead of promising unsupported performance.
- [ ] Replace the native-app-first README with browser instructions and screenshot evidence. Explain schematic layout/width adjustments, checkpoints versus legacy fitness, driver compatibility, and the later F1 sprite workflow. Update the two-minute interview walkthrough.
- [ ] Commit verified changes on a feature branch, publish to the existing authorized repository with a checked remote-head update, and reconcile local/remote history. Use the working GitHub connector if CLI authentication is still unavailable; do not request sign-in again without evidence it is necessary. Verify the published tree matches tested files.
- [ ] Refresh `outputs/neat-car-simulation.zip` from tracked deliverables only. Exclude environments, logs, saves, and scratch files. Return the repository link, browser launch instructions, and concise limitations.

## Execution recommendation

Recommend Native execution: implement these tasks in this session, with a fresh review of the complete change before publication. The settings, geometry, controller, and interface share close boundaries; keeping implementation in one session makes those boundaries easier to maintain. A subagent-driven approach is also available if Omar prefers independent review after each task.

Omar approved this plan and selected subagent-driven execution. The implementation
and release documentation are now prepared; the controller completes the final
review, authorized publication, history reconciliation, and download ZIP refresh.
