"""Validated simulation settings; visual preferences live outside experiments."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math


@dataclass(frozen=True)
class ExperimentSettings:
    max_speed: float = 18
    steering_step: float = 5
    sensor_range: float = 300
    population: int = 30
    seed: int = 7
    episode_steps: int = 1200
    road_width: float = 120

    def __post_init__(self):
        bounds = {"max_speed": (6, 24), "steering_step": (1, 10),
                  "sensor_range": (100, 600), "population": (10, 100),
                  "seed": (0, 2147483647), "episode_steps": (300, 3600),
                  "road_width": (90, 180)}
        integers = {"population", "seed", "episode_steps"}
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not minimum <= value <= maximum or not math.isfinite(value)
                    or (name in integers and type(value) is not int)):
                raise ValueError(f"{name} must be a finite "
                                 f"{'integer' if name in integers else 'number'} "
                                 f"between {minimum} and {maximum}")
            # Equivalent JSON numbers (18 and 18.0) have the same identity.
            if name not in integers:
                object.__setattr__(self, name, float(value))

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Experiment settings must be an object")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("Unknown experiment settings")
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)

    def fingerprint(self, track_id: str, geometry_revision: str, reward_version: str) -> str:
        for name, value in (("track_id", track_id), ("geometry_revision", geometry_revision),
                            ("reward_version", reward_version)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        data = {"settings": self.to_dict(), "track_id": track_id,
                "geometry_revision": geometry_revision, "reward_version": reward_version}
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
