# Browser demo design

Status: approved and implemented on `feature/browser-demo`, October 12, 2026.
This document preserves the agreed design and its original requirements as a
historical record. Current behavior and verification limits are documented in
README.md and docs/VERIFICATION.md; final review and publication are release gates.

## Intended result

Omar can double-click Launch.bat and demonstrate the self-driving experiment in a local browser during a mock interview. The track occupies most of the screen; switching tracks, changing colors, and explaining what the network sees are easy. Advanced controls support experiments without crowding the presentation. The existing tutorial attribution and AI assistance disclosure stay visible in the GitHub documentation. Omar will help select actual F1 car artwork later.

Success means a reliable launch, smooth rendering, understandable controls, genuine Python NEAT training, and an immediately available saved-driver demonstration. Browser rendering is an opportunity to improve presentation; it does not by itself make the driving physics more realistic.

## Recommended approach and alternatives

Use a local Python server with a small HTML/CSS/JavaScript interface and Canvas 2D rendering. Keep the current NEAT, numeric driver files, sensors, and simulation logic. This avoids a second learning implementation and an additional Node installation for Omar. Canvas supports sharp rendering at the display's resolution, car rotation, vector roads, sensors, and camera controls. Local assets and system fonts allow operation offline after setup.

A React/Vite interface could support a larger application, but adds a build pipeline that this demo does not currently need. A full JavaScript simulation would simplify hosting a future online demo, but would require porting or replacing the existing Python evolution implementation. Neither is selected for this revision.

## Launch and runtime

- Launch.bat starts the Python server, waits until it is ready, and opens the default browser at a loopback address such as http://127.0.0.1:8765. If that port belongs to another application, select an available port. Repeated launches reuse a verified project server rather than opening competing simulations.
- Add aiohttp for local HTTP and WebSocket transport; select and pin a compatible release during implementation. Setup.bat remains the installation entry point. Run Pygame headlessly for the existing collision masks; no separate Pygame window is needed.
- The server owns one simulation session. It sends snapshots containing generation, fitness, living cars, positions, headings, and the selected car's sensor endpoints. Browser controls send validated commands. Reloading the page reconnects to the current session.
- Physics advances in fixed steps. Browser animation runs independently with requestAnimationFrame and interpolates within the same episode. Restart or generation changes reset interpolation. If the machine cannot keep up, report the effective simulation rate rather than changing physics to compensate.
- Include a Stop server control, connection status, useful launch errors, and logs. Bound the service to loopback and validate incoming settings. No online service is needed to train or replay.

## Screen and controls

Use a restrained motorsport timing-screen style: dark charcoal controls, clear typography, one accent color, and a large illustrated track. Avoid decorative dashboard cards that compete with the simulation.

The main controls are track selection with previews, Replay/Train, Start or Pause, Restart, playback speed, car color, and Fullscreen. Default to the verified Classic saved-driver replay so Omar can demonstrate motion immediately. Label replay, live training, and transfer tests clearly. A compact information strip shows generation, alive/population, fitness, and connection state. An optional inspector explains the five sensor readings and selected driving action.

Support fit-to-track, zoom, and a follow-leading-car camera. A presentation toggle hides detailed controls. Sensors, trails, checkpoints, turn numbers, and sector colors are independent overlays. Keyboard controls retain useful existing shortcuts, and form fields do not accidentally trigger simulation shortcuts.

## Advanced section

Advanced is collapsed initially, with three groups:

1. Appearance: custom car/accent color, asphalt and surrounding colors for vector circuits, sensor/trail visibility and opacity, and camera behavior. Changes apply immediately and do not alter training.
2. Driving experiment: maximum speed, steering step, and sensor range. Keep five sensors and four outputs so the network's interface remains understandable. Show values in simulation units, not invented real-world km/h. Default legacy settings reproduce the current Classic driver.
3. Training: population size (10–100), random seed, episode limit (300–3,600 steps), and reset to defaults. Show the current effective settings. Applying driving/training changes explicitly starts a new experiment; opening or editing the panel alone does not reset anything.

Save visual preferences in the browser. Store an experiment fingerprint with new drivers, including physics settings, track geometry revision, and reward version. Replay must reject incompatible settings with a useful explanation and offer the driver's compatible preset. Load old numeric files only with their original settings. Use separate save locations so modified experiments cannot replace the established demo accidentally. Validate settings on the server as well as in the UI.

## F1 circuits: what fits the current experiment

Start with original, editable vector approximations of the Monza and Silverstone Grand Prix layouts. Bahrain's Sakhir Grand Prix layout is the next candidate. These are schematic educational reconstructions informed by official reference maps, not surveyed reproductions or official artwork.

| Circuit reference | Real layout facts | What the experiment gains |
| --- | --- | --- |
| Monza | 5.793 km; 11 turns; long straights and tight chicanes | Braking and alternating turns |
| Silverstone | 5.891 km; 18 turns; fast flowing sequences including Maggotts and Becketts | Sustained steering and direction changes |
| Bahrain International Circuit, Sakhir GP layout | 5.412 km; 15 turns | A later contrasting layout with tighter corners |

These facts describe the reference circuits, not the measured length or exact corner geometry of our approximations. Choose the GP layout explicitly; a venue name alone can refer to multiple configurations. Do not infer track geometry from the current generic bitmap filenames.

Each new circuit has a versioned data file: source URL, reference layout/year, normalized centerline points, driving direction, adjustable road width, start position and heading, ordered checkpoint gates, and sector/turn labels. Preserve aspect ratio. Use the same sampled centerline and world transform to generate the visible asphalt and the separate drivable mask. Kerbs, grass, gravel, painted lines, and labels are decoration; they cannot silently change collision behavior.

Provide a wider training preset to make chicanes learnable with this simple steering model. The UI identifies width adjustments and schematic geometry. Validate the spawn footprint, corners, adjacent sections, and road continuity at each supported width. Keep the 11 existing bitmap tracks available under Original tracks.

New vector circuits use ordered checkpoints for forward progress and lap completion. A checkpoint is accepted only after the previous one, in the intended direction; crossing the finish line alone cannot count a lap. Penalize or stop prolonged lack of progress. Original tracks retain their current distance fitness to preserve the bundled driver. Distance fitness can reward circling, so documentation explains why new circuits use a different reward and why their scores are not directly comparable.

Do not display a trained F1-circuit driver until it has actually been trained and verified. Live training on a new circuit can be demonstrated even if its first generations fail. Guaranteed replay remains available on Classic.

## Cars and realism

Prepare a later sprite interface with separate artwork, rotation anchor, display size, and collision footprint. An F1 top view needs a narrow nose, exposed wheels, cockpit, sidepods, and front/rear wings. Wheelbase measures axle spacing, not the car's overall length. FIA's 2026 introductory dimensions provide a useful proportion reference, but exact team artwork and final dimensions need their own chosen source before import.

For this revision, retain the existing cars and improve browser scaling and colors. Omar will select actual F1 car images later. Record their provenance when added. Artwork changes should not alter driving behavior unless the experiment explicitly changes its collision footprint. This stays a flat sensor-based NEAT experiment; elevation, tyre dynamics, aero, power units, and competitive racing are future work.

## Review and verification criteria

- Test startup, repeated launch, port conflict, page reload/reconnect, pause/restart, track switching, color changes, Advanced reset/apply, fullscreen, resize, and keyboard controls in an actual browser.
- Run existing simulation tests and verify the bundled Classic driver's survival and coverage under unchanged default settings.
- Verify each vector circuit's geometry and safe spawn; test checkpoints against reversed, repeated, and out-of-order crossings.
- Test driver/settings compatibility, malformed commands, and save separation. Complete at least one genuine generation on each new circuit.
- Observe rendering and simulation responsiveness on Omar's machine; show lower simulation throughput honestly if needed.
- Update README, attribution, interview notes, screenshots, and launch instructions around the browser experience; publish the verified changes to the existing GitHub repository and refresh the download ZIP.

## Research sources

Reviewed October 10, 2026. Reference artwork is consulted rather than bundled automatically.

- [Formula 1: Monza circuit guide, September 3, 2026](https://www.formula1.com/en/latest/article/circuit-guide-everything-you-need-to-know-about-the-autodromo-nazionale-monza.51PKqBRlxNs0fzLWQzsnd0.51PKqBRlxNs0fzLWQzsnd0): reference length, turns, corner character, and detailed circuit map.
- [Formula 1: Silverstone circuit guide, July 2, 2026](https://www.formula1.com/en/latest/article/circuit-guide-everything-you-need-to-know-about-silverstone-2026.5Sl0O8g393enBWVIkjRzOr): reference length, turns, driving character, and circuit map.
- [Formula 1: Bahrain International Circuit information](https://ticketing.formula1.com/bahrain/): Sakhir's GP circuit length and turn count; used as a venue/layout reference, not a claim about the current season's calendar.
- [FIA: 2026 regulations introduction, June 6, 2024](https://api.fia.com/news/new-era-competition-fia-showcases-future-focused-formula-1-regulations-2026-and-beyond): introductory maximum wheelbase 3,400 mm and width 1,900 mm. This is an early design reference, not a substitute for current technical rules or overall car length.
- [FIA: current 2026 regulation documents](https://www.fia.com/regulation/category/2182): lists technical Issue 20 dated August 5, 2026, published October 1. The latest PDF was unavailable through the research tool, so exact current dimension compliance is not asserted.
