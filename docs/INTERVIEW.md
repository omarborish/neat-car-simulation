# Interview rehearsal

## A two-minute browser demonstration

1. **0:00–0:20:** Open `Launch.bat` before the call. On a fresh install Classic
   saved replay starts immediately. Select red, enable Show leader sensors,
   and open Sensor inspector. Explain the bundled driver was actually trained
   and checked for 1,200 steps with circuit coverage.
2. **0:20–0:45:** Pause. Show the five normalized wall distances and chosen action:
   left, right, brake, or accelerate. Resume and change color to demonstrate
   appearance preserves the policy and progress.
3. **0:45–1:15:** Select Monza or Silverstone. A fresh install starts Train because
   no compatible study champion is bundled. Each car is a candidate network;
   NEAT evolves the population between generations. Early crashes are expected.
   Show ordered laps and checkpoint fitness without promising a successful lap.
4. **1:15–1:40:** Pause and open Advanced. Change a driving/training draft field
   and point to unchanged applied values. Reset defaults in draft, then click
   Apply and restart training to show an explicit new experiment. Appearance
   changes apply immediately instead.
5. **1:40–2:00:** Return to Classic. If the active preset is incompatible, choose
   Replay, then Restore compatible preset and replay. Confirm the Classic training
   label and compatible applied values. Use Presentation for a clean closing view.

Local study champions can make track selection choose Replay; use Train explicitly
when demonstrating evolution. Test Classic driver here is a **transfer test**:
source saved fitness was measured on Classic, not the target. Stop server at the
end. Keep 1× for a predictable rehearsal.

## A candid introduction

"I started from NeuralNine's NEAT car simulation, which credits Cheesy AI.
I extended it into a local browser demo with camera and sensor controls,
validated experiment presets, isolated saved drivers, and schematic circuit
studies with ordered checkpoint progress. I used AI assistance for these changes.
I can explain how the five sensor inputs become four driving choices and show
the tests and observed results."

Only describe additions you have reviewed and understand. Do not claim you invented
NEAT, the original tutorial, or official circuit artwork.

## Questions to prepare for

**What does NEAT learn?** It evolves weights and network structure. Candidate
networks drive cars; fitness guides selection and speciation preserves diversity.
There is no labelled training set.

**Why does replay work without retraining?** Numeric JSON stores the evaluated
feed-forward network's biases, responses, connections and weights. Replay uses
the same sensor/physics loop. It does not restore an evolutionary population.

**Why use a Python server?** Python remains the authority for physics and real
NEAT evolution. One worker owns the shared session. HTTP commands return
acknowledgements; WebSockets stream snapshots. Canvas draws and interpolates
within episodes independently. Reload reconnects without restarting training.

**Why two fitness objectives?** Bitmap tracks retain distance/60 to preserve the
legacy demo. Distance can reward circling. Study circuits require forward ordered
gate crossings and all preceding gates before a finish crossing counts as a lap.
Bounded partial progress gives feedback without repeated movement accumulating
credit. The objectives have different scales; compare only the same experiment.

**How are saves protected?** Browser format-2 champions go under a fingerprint
separate from bundled/legacy saves. Normal replay checks track, all settings,
physics version, geometry and reward revision. Restore compatible preset deliberately
adopts a driver's settings. Transfer is explicit and requires compatible physics.

**How were controls tested?** Tests cover real simulation, saved networks,
commands, sockets and launcher lifecycle. Actual Chrome checks showed pause,
color, track changes, draft/apply/reset, camera, reload and shutdown. Fullscreen
was rejected by the scripted browser; Presentation worked. See
[VERIFICATION.md](VERIFICATION.md) for evidence and remaining manual checks.

**What are the limits?** Simplified 2D dynamics, five wall-distance inputs with
no camera or speed input, and schematic geometry. The studies are not exact GP
tracks. Classic survived the checked episode; both early study champions crashed
with zero laps. Neither establishes general driving ability. Throughput depends
on the machine; rendering frame rate was not measured.

**What would you do next?** Train/evaluate study drivers across repeated seeds
and held-out circuits, measure lap success and runtime, and compare changes under
the same conditions. Separately, select permitted top-down F1 artwork with Omar
and record its provenance without silently changing collision dimensions.

## Before the call

- Rehearse at the window size you will share and confirm Connected.
- Start with compatible Classic replay, sensors on and speed 1×.
- Explain Advanced drafts and distinguish reference kilometres from simulation units.
- Keep the README, source and verification notes available for questions.
- Rehearse Presentation; check Fullscreen manually in your browser if needed.
- Keep the old recording or native `python app.py` as a fallback.
