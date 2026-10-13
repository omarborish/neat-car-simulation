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

The browser extension adds a local aiohttp server, a single simulation worker,
Canvas rendering and camera controls, validated Advanced presets, compatible
format-2 driver saves isolated from the bundled demo, and ordered checkpoints
for two new circuit studies. AI assistance was also used to implement, test,
review, and document this extension. The browser screenshots under `docs/`
are captures of the running local app, not generated interface mockups.

## Circuit studies and reference material

`assets/circuits/monza.json` and `assets/circuits/silverstone.json` are original,
editable educational schematics informed by the linked Formula 1 reference
guides and diagrams, reviewed October 10, 2026. Official map artwork was
consulted, not bundled. Circuit names describe the chosen Grand Prix reference
layouts; the supplied roads are not surveyed reproductions or official artwork.

- [Formula 1 Monza guide](https://www.formula1.com/en/latest/article/circuit-guide-everything-you-need-to-know-about-the-autodromo-nazionale-monza.51PKqBRlxNs0fzLWQzsnd0.51PKqBRlxNs0fzLWQzsnd0)
  and [reference diagram](https://media.formula1.com/image/upload/c_lfill%2Cw_3392/q_auto/v1740000001/fom-website/2026/Italy/2026trackmonzadetailed.webp):
  GP reference 5.793 km and 11 turns. Bends/chicanes use a wider schematic road
  envelope for the simplified car.
- [Formula 1 Silverstone guide](https://www.formula1.com/en/latest/article/circuit-guide-everything-you-need-to-know-about-silverstone-2026.5Sl0O8g393enBWVIkjRzOr)
  and [reference diagram](https://media.formula1.com/image/upload/c_lfill%2Cw_3392/q_auto/v1740000001/fom-website/2026/Circuit%20maps/2026tracksilverstonedetailed.webp):
  GP reference 5.891 km and 18 turns. The inner loop and northern hairpin were
  opened, and the outer right section spaced outward, to separate road stretches
  at the 90/120/180-unit presets. Reference kilometres are not simulation units.

These references do not grant rights to reuse third-party artwork or branding.
The existing tutorial/asset license context above still applies.

## Deferred artwork

New top-down F1 artwork will be chosen manually with the project owner later.
Record the artist/source and permission for each new asset here before adding it.
