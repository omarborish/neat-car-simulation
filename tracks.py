"""Track names, files and starting positions are kept in one small registry."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

from simulator import Car, Track

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TrackSpec:
    id: str
    name: str
    filename: str
    start: tuple = (860, 950)
    angle: float = 0


TRACKS = (
    TrackSpec("classic", "Classic circuit", "map.png"),
    TrackSpec("track02", "Circuit 02", "map2.png"),
    TrackSpec("track03", "Circuit 03", "map3.png"),
    TrackSpec("track04", "Circuit 04", "map4.png"),
    TrackSpec("track05", "Circuit 05", "map5.png"),
    TrackSpec("track07", "Circuit 07", "map7.png"),
    TrackSpec("track08", "Circuit 08", "map8.png"),
    TrackSpec("track09", "Circuit 09", "map9.png"),
    TrackSpec("purple", "Purple circuit", "mappurple.png"),
    TrackSpec("rectangle", "Rectangle", "maprec.png"),
    TrackSpec("practice", "Practice circuit", "maptest.png"),
)


def get_spec(track_id):
    for spec in TRACKS:
        if spec.id == track_id:
            return spec
    raise ValueError(f"Unknown track: {track_id}")


@lru_cache(maxsize=16)
def load_track(track_id, road_width=120):
    if track_id in ("monza", "silverstone"):
        from circuits import load_circuit
        return load_circuit(track_id, road_width)
    spec = get_spec(track_id)
    path = ROOT / "assets" / "tracks" / spec.filename
    if not path.is_file():
        raise ValueError(f"Missing track image: {spec.filename}")
    track = Track(pygame.image.load(str(path)), spec.start, spec.angle, spec.id)
    if Car(track).collides():
        raise ValueError(f"The starting position for {spec.name} touches a wall")
    return track
