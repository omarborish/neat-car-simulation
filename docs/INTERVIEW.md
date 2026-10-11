# Interview rehearsal

## A two-minute demonstration

1. Open `Launch.bat` before the interview and check that the menu appears.
2. Select Classic circuit, red, and Replay saved. Start replay. This avoids
   spending interview time waiting for an evolutionary run.
3. Press S to show the leading car's five distance sensors. Point out the sensor
   bars, the four possible actions, and the training-track label.
4. Press Space to pause while explaining how sensor distances become network
   inputs. Press Space again to resume.
5. Press C to change color. Explain that rendering is independent of the policy.
6. Return to the menu and start Train live. Explain that each car represents a
   candidate network and the population is evolved between generations.
7. If time permits, try another circuit in replay. Call this a transfer test,
   rather than promising that the saved driver will succeed on unseen tracks.

## A candid introduction

"I started from NeuralNine's NEAT car simulation, which itself credits Cheesy AI.
I extended the project into an easier live demo: track and color selection,
presentation controls, safe boundaries, and saving/replaying trained drivers.
I used AI assistance for this upgrade. I can walk through how the five sensor
values become four driving choices and how I tested the new controls."

Only describe additions you have reviewed and understand. Use the code map in
the README to prepare; do not claim you invented NEAT or the original tutorial.

## Questions to prepare for

**What does NEAT learn?**
It evolves network weights and can add/remove nodes and connections. Each
candidate network is evaluated by driving a car. Fitness drives selection, and
speciation helps preserve different network structures during evolution.

**What are the inputs and outputs?**
Five normalized distances to bitmap walls. Four outputs, with the maximum
choosing left, right, brake, or accelerate. There is no labelled training set.

**Why does replay work without training again?**
The saved JSON contains the evaluated feed-forward network's biases, responses,
connections and weights. Replay reconstructs that policy and runs the same
sensor/movement loop. It does not restore an entire NEAT population.

**What did you improve in the simulation?**
Boundary pixels are treated as walls instead of indexing outside the image.
Speed is capped, movement checks use substeps, and collision coordinates do not
depend on display scaling. Fitness is assigned from total distance, avoiding
repeated accumulation of all past distance each frame.

**How do you know the controls work?**
The tests send real Pygame events. They check that pause freezes simulation time,
color changes preserve positions, track changes start a new population, and
mouse input still reaches the correct button at a smaller window size.

**What are the limitations?**
Distance alone is an imperfect objective: a car can drive repeatedly in a small
region. There are no ordered checkpoints or lap checks, and the vehicle dynamics
are simplified. A driver trained on one track can fail on another. The bundled
driver was checked for 20 seconds on Classic, not validated as a general driver.

**What would you do next?**
Add ordered checkpoints to make progress measurable, evaluate on held-out
circuits, and then compare changes under the same seeds and time limit. Separately,
replace the existing visual sprites with manually chosen top-down F1 cars.

## Before the call

- Rehearse once with the same monitor/window size you will share.
- Start with the bundled Classic replay and turn sensors on.
- Keep the README and source open for questions.
- Keep the old recording as a fallback, if you want to use it.
- Say which behavior is verified and which is a demonstration or limitation.
