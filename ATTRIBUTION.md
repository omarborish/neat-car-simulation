# Sources and attribution

## Tutorial starting point

- Repository: [NeuralNine/ai-car-simulation](https://github.com/NeuralNine/ai-car-simulation)
- Source: [newcar.py](https://github.com/NeuralNine/ai-car-simulation/blob/master/newcar.py)
- Tutorial author: Florian Dedov (NeuralNine).
- The upstream source explicitly credits Cheesy AI for inspiration.
- Tutorial video: [NeuralNine's AI car simulation](https://www.youtube.com/watch?v=Cy155O5R1Oo).

The existing May 2025 local project was the starting point for this presentation
upgrade. The source uses the same five-ray/four-action NEAT experiment as the
tutorial. The following local files were verified against the upstream Git blob
IDs on October 10, 2026. They match byte-for-byte:

| Original file | Upstream Git blob |
| --- | --- |
| `car.png` | `8245b1949abdc48226d053fa1516aae02a80596a` |
| `config.txt` (before this upgrade) | `c0f578df731297e27554715dae4317e9af09ddb8` |
| `map.png` | `85d403b1f1bf052ad8c8d0f3b6a5b4b550822fbe` |
| `map2.png` | `f28a8ba962c632c189d8eb3c1e9cbcdd7a2b6129` |
| `map3.png` | `8034c5e0cf2428ba1d009abd24527c57f71dbbe3` |
| `map4.png` | `6fc2a927e8d45a0a910baab4212db41c09030410` |
| `map5.png` | `ba3ece3d2626b93fa3218305eaa9fccda163f4a3` |

The copied images are now under `assets/`. This version's `config.txt` makes
neat-python's previously implicit default values explicit. Additional maps and
colored car variants came from the owner's existing local project; their original
authors have not been independently verified, so they are not claimed as newly
created artwork.

The public upstream repository had no license file or detected license at the
time of inspection. This repository does not invent a license grant for those
materials. Attribution describes provenance; it does not assign ownership or
change third-party rights.

## This presentation upgrade

Added for this version: native menu and controls, safe bitmap queries, capped
speed, incremental distance fitness, fixed-coordinate simulation, numeric JSON
exports, replay with training-track labels, launcher/setup scripts, tests and
documentation. AI assistance was used to implement and verify these additions.
The original desktop project has been left in its original folder.

## Deferred artwork

New top-down F1 artwork will be chosen manually with the project owner later.
Record the artist/source and permission for each new asset here before adding it.
