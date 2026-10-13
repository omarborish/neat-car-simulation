"""Single-owner browser session controller; no networking or rendering state."""
from copy import deepcopy
import math
from pathlib import Path
from uuid import uuid4

from models import compatible_driver, experiment_metadata, load_driver
from settings import ExperimentSettings
from simulator import Car, COLORS, choose_action
from tracks import ROOT, load_track
from training import Session


class ReplayUnavailable(ValueError):
    def __init__(self, message, preset=None):
        super().__init__(message)
        self.preset = preset


class Runtime:
    """Mutations and steps must be called by the server's one simulation worker."""
    def __init__(self, save_dir: Path):
        self.save_dir = Path(save_dir)
        self.settings = ExperimentSettings()
        self.color = "mixed"
        self.show_sensors = True
        self.multiplier = 1
        self.paused = False
        self._start("classic", "replay", self.settings)

    @property
    def step_rate(self):
        return 60 * self.multiplier

    def _candidates(self, track_id, track, settings, include_other=False):
        fingerprint = experiment_metadata(track, settings)["fingerprint"]
        paths = [self.save_dir / "experiments" / fingerprint / f"{track_id}.json",
                 self.save_dir / f"{track_id}.json", ROOT / "demos" / f"{track_id}.json"]
        if include_other:
            paths.extend(sorted((self.save_dir / "experiments").glob(f"*/{track_id}.json")))
        for path in dict.fromkeys(paths):
            if path.is_file():
                try:
                    driver = load_driver(path)
                except ValueError:
                    continue
                if driver.track_id == track_id:
                    yield driver, path

    def _driver(self, track, settings, transfer=False, source_track_id=None, restore=False):
        source_id = source_track_id if transfer else track.id
        source = load_track(source_id, settings.road_width) if transfer else track
        preset = None
        for driver, path in self._candidates(source.id, source, settings, include_other=True):
            candidate_settings = (ExperimentSettings.from_dict(driver.experiment["settings"])
                                  if driver.experiment else ExperimentSettings())
            if preset is None:
                preset = candidate_settings.to_dict()
            effective = candidate_settings if restore else settings
            target = load_track(track.id, effective.road_width) if restore else track
            if compatible_driver(driver, target, effective, transfer=transfer):
                return driver, path, effective, target
        raise ReplayUnavailable("No compatible champion for this track and settings. "
                                "Train a champion or restore compatible settings.", preset)

    def _start(self, track_id, mode, settings, transfer=False, source_track_id="classic", restore=False):
        if not isinstance(track_id, str):
            raise ValueError("track_id must be a track name")
        if mode not in (None, "train", "replay"):
            raise ValueError("mode must be train or replay")
        track = load_track(track_id, settings.road_width)
        driver = path = session = car = None
        if mode != "train":
            try:
                driver, path, settings, track = self._driver(
                    track, settings, transfer, source_track_id, restore)
                mode = "replay"
            except ReplayUnavailable:
                if mode == "replay":
                    raise
                mode = "train"
        if mode == "train":
            session = Session(track_id, self.color, settings.seed, self.save_dir, settings=settings)
            track = session.track
        else:
            car = Car(track, "red" if self.color == "mixed" else self.color, settings)
        # Publish only after every setting, track and replay check succeeds.
        self.settings, self.track, self.mode = settings, track, mode
        self.session, self.car, self.driver = session, car, driver
        self.replay_path = path
        self.transfer = transfer and driver is not None and driver.track_id != track_id
        self.session_id, self.episode_id = uuid4().hex, uuid4().hex
        self.paused = False

    def command(self, data: dict) -> dict:
        try:
            if not isinstance(data, dict) or not isinstance(data.get("command"), str):
                raise ValueError("Provide an object with a command name")
            name = data["command"]
            fields = {"pause": set(), "resume": set(), "restart": set(),
                      "start": {"track_id", "mode"}, "appearance": {"color", "sensors"},
                      "apply_settings": {"settings"}, "speed": {"multiplier"},
                      "transfer_test": {"track_id", "source_track_id"},
                      "restore_compatible": {"track_id"}}
            if name not in fields:
                raise ValueError(f"Unknown command: {name}")
            if set(data) - fields[name] - {"command"}:
                raise ValueError(f"Unknown fields for {name}")
            if name in ("pause", "resume"):
                self.paused = name == "pause"
            elif name == "appearance":
                color = data.get("color", self.color)
                sensors = data.get("sensors", self.show_sensors)
                if color not in COLORS or type(sensors) is not bool:
                    raise ValueError("Choose a supported car color and a boolean sensors value")
                self.color, self.show_sensors = color, sensors
                if self.session:
                    self.session.set_color(color)
                else:
                    self.car.color = "red" if color == "mixed" else color
            elif name == "speed":
                multiplier = data.get("multiplier")
                if type(multiplier) not in (int, float) or multiplier not in (1, 4):
                    raise ValueError("Speed multiplier must be 1 or 4")
                self.multiplier = multiplier
            elif name == "apply_settings":
                updates = data.get("settings")
                if not isinstance(updates, dict):
                    raise ValueError("Provide settings to apply")
                settings = ExperimentSettings.from_dict({**self.settings.to_dict(), **updates})
                self._start(self.track.id, "train", settings)
            elif name == "restart":
                self._start(self.track.id, self.mode, self.settings, self.transfer,
                            self.driver.track_id if self.driver else "classic")
            else:
                track_id = data.get("track_id", self.track.id)
                self._start(track_id, "replay" if name != "start" else data.get("mode"),
                            self.settings, transfer=name == "transfer_test",
                            source_track_id=data.get("source_track_id", "classic"),
                            restore=name == "restore_compatible")
            return {"ok": True, "snapshot": self.snapshot()}
        except (ValueError, TypeError) as error:
            result = {"ok": False, "error": str(error), "snapshot": self.snapshot()}
            if isinstance(error, ReplayUnavailable) and error.preset is not None:
                result["compatible_settings"] = error.preset
            return result

    def step(self) -> None:
        if self.paused:
            return
        if self.session:
            if self.session.step():
                self.episode_id = uuid4().hex
        else:
            self.car.step(choose_action(self.driver.network, self.car))
            if not self.car.alive or self.car.steps >= self.settings.episode_steps:
                self.car = Car(self.track, "red" if self.color == "mixed" else self.color, self.settings)
                self.episode_id = uuid4().hex

    def snapshot(self) -> dict:
        agents = ([(index, agent.car, agent.network) for index, agent in enumerate(self.session.agents)]
                  if self.session else [(0, self.car, self.driver.network)])
        cars = [{"id": index, "position": list(car.position), "angle": car.angle,
                 "speed": car.speed, "color": car.color, "alive": car.alive,
                 "fitness": car.fitness, "distance": car.distance, "steps": car.steps,
                 "laps": car.progress.laps if car.progress else 0,
                 "sensors": [{"end": list(end), "distance": distance}
                             for end, distance in car.radars],
                 "inputs": car.inputs(), "action": choose_action(network, car)}
                for index, car, network in agents]
        leader = max(cars, key=lambda car: car["fitness"])
        saved = self.session.saved_fitness if self.session else self.driver.fitness
        replay = None if self.session else {
            "training_track_id": self.driver.track_id, "transfer": self.transfer,
            "generation": self.driver.generation, "fitness": self.driver.fitness,
            "seed": self.driver.seed, "format_version": 2 if self.driver.experiment else 1,
            "source": "bundled" if self.replay_path.parent == ROOT / "demos" else "saved",
            "experiment": self.driver.experiment}
        return deepcopy({"schema_version": 1, "session_id": self.session_id,
                         "episode_id": self.episode_id, "mode": self.mode, "paused": self.paused,
                         "track_id": self.track.id, "settings": self.settings.to_dict(),
                         "experiment": experiment_metadata(self.track, self.settings),
                         "generation": self.session.generation if self.session else self.driver.generation,
                         "population": len(cars), "alive": sum(car["alive"] for car in cars),
                         "fitness": {"current": leader["fitness"],
                                     "best": self.session.best_fitness if self.session else self.driver.fitness,
                                     "last_generation": self.session.last_generation_fitness if self.session else None,
                                     "saved": saved if math.isfinite(saved) else None},
                         "cars": cars, "leader": {"id": leader["id"], "sensors": leader["sensors"],
                                                   "inputs": leader["inputs"], "action": leader["action"]},
                         "laps": leader["laps"], "replay": replay,
                         "appearance": {"color": self.color, "sensors": self.show_sensors},
                         "speed_multiplier": self.multiplier, "step_rate": self.step_rate,
                         "effective_step_rate": 0 if self.paused else self.step_rate})
