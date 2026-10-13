"""Observable browser behavior over actual cars, drivers, and NEAT sessions."""
import importlib
import importlib.util
import json
from pathlib import Path
import unittest

from models import load_driver, save_driver
from settings import ExperimentSettings
from tracks import ROOT
from training import Session
from workspace_temp import WorkspaceTemp


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("runtime"),
                             "Browser runtime is not implemented")
        self.folder = WorkspaceTemp()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.runtime = importlib.import_module("runtime").Runtime(self.directory)

    def command(self, name, **fields):
        result = self.runtime.command({"command": name, **fields})
        self.assertTrue(result["ok"], result.get("error"))
        return result["snapshot"]

    def test_initial_classic_replay_moves_and_snapshot_is_independent_json(self):
        initial = self.runtime.snapshot()
        self.assertEqual(initial["schema_version"], 1)
        self.assertEqual(initial["mode"], "replay")
        self.assertEqual(initial["track_id"], "classic")
        self.assertFalse(initial["paused"])
        self.runtime.step()
        self.assertNotEqual(initial["cars"][0]["position"],
                            self.runtime.snapshot()["cars"][0]["position"])
        initial["settings"]["max_speed"] = 999
        self.assertEqual(self.runtime.snapshot()["settings"]["max_speed"], 18)
        json.dumps(self.runtime.snapshot(), allow_nan=False)

    def test_pause_freezes_and_resume_moves(self):
        paused = self.command("pause")
        for _ in range(5):
            self.runtime.step()
        self.assertEqual(self.runtime.snapshot(), paused)
        self.command("resume")
        self.runtime.step()
        self.assertNotEqual(paused["cars"], self.runtime.snapshot()["cars"])

    def test_color_preserves_training_and_position(self):
        self.command("start", track_id="monza", mode="train")
        self.runtime.step()
        before = self.runtime.snapshot()
        after = self.command("appearance", color="purple", sensors=False)
        for field in ("session_id", "episode_id", "generation", "fitness", "settings"):
            self.assertEqual(before[field], after[field])
        self.assertEqual([car["position"] for car in before["cars"]],
                         [car["position"] for car in after["cars"]])
        self.assertTrue(all(car["color"] == "purple" for car in after["cars"]))

    def test_restart_same_seed_reproduces_early_training(self):
        self.command("start", track_id="classic", mode="train")
        for _ in range(10):
            self.runtime.step()
        before = self.runtime.snapshot()
        restart = self.command("restart")
        self.assertNotEqual(before["session_id"], restart["session_id"])
        for _ in range(10):
            self.runtime.step()
        self.assertEqual(before["cars"], self.runtime.snapshot()["cars"])

    def test_apply_settings_resets_session_and_uses_population_episode(self):
        before = self.runtime.snapshot()
        after = self.command("apply_settings", settings={"population": 10,
                             "episode_steps": 300, "seed": 12})
        self.assertNotEqual(before["session_id"], after["session_id"])
        self.assertEqual(after["population"], 10)
        self.assertEqual(after["settings"]["episode_steps"], 300)
        self.assertEqual(after["mode"], "train")

    def test_bad_commands_leave_session_untouched(self):
        before = self.runtime.snapshot()
        for data in (None, {}, {"command": "unknown"},
                     {"command": "start", "track_id": "unknown"},
                     {"command": "appearance", "color": "nope"},
                     {"command": "apply_settings", "settings": {"population": 1}},
                     {"command": "start", "track_id": "monza", "mode": "replay"},
                     {"command": "speed", "multiplier": 100},
                     {"command": "speed", "multiplier": 2},
                     {"command": "pause", "unexpected": True}):
            with self.subTest(data=data):
                result = self.runtime.command(data)
                self.assertFalse(result["ok"])
                self.assertTrue(result["error"])
                self.assertEqual(before, self.runtime.snapshot())

    def test_new_track_trains_and_transfer_requires_explicit_compatible_physics(self):
        snapshot = self.command("start", track_id="silverstone")
        self.assertEqual(snapshot["mode"], "train")
        snapshot = self.command("transfer_test", track_id="silverstone")
        self.assertEqual(snapshot["replay"]["training_track_id"], "classic")
        self.assertTrue(snapshot["replay"]["transfer"])
        self.assertEqual(snapshot["track_id"], "silverstone")
        self.command("apply_settings", settings={"max_speed": 20})
        before = self.runtime.snapshot()
        self.assertFalse(self.runtime.command({"command": "transfer_test",
                                             "track_id": "monza"})["ok"])
        self.assertEqual(before, self.runtime.snapshot())

    def test_replay_reset_changes_episode_id_and_speed_does_not_change_physics(self):
        before = self.runtime.snapshot()
        faster = self.command("speed", multiplier=4)
        self.assertEqual(faster["step_rate"], 240)
        self.assertEqual(before["cars"], faster["cars"])
        self.assertEqual(before["session_id"], faster["session_id"])
        for _ in range(1200):
            self.runtime.step()
        after = self.runtime.snapshot()
        self.assertNotEqual(before["episode_id"], after["episode_id"])
        self.assertEqual(before["session_id"], after["session_id"])
        self.assertEqual(after["cars"][0]["steps"], 0)

    def test_custom_training_save_is_isolated_format_two_and_replayable(self):
        demo = (ROOT / "demos" / "classic.json").read_bytes()
        legacy = self.directory / "classic.json"
        legacy.write_bytes(demo)
        self.command("apply_settings", settings={"population": 10, "episode_steps": 300})
        generation = self.runtime.snapshot()["generation"]
        for _ in range(300):
            self.runtime.step()
            if self.runtime.snapshot()["generation"] != generation:
                break
        self.assertEqual(self.runtime.snapshot()["generation"], generation + 1)
        paths = list((self.directory / "experiments").glob("*/classic.json"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_text())["format_version"], 2)
        self.assertEqual(legacy.read_bytes(), demo)
        self.assertEqual((ROOT / "demos" / "classic.json").read_bytes(), demo)
        self.assertEqual(self.command("start", track_id="classic")["mode"], "replay")

    def test_incompatible_replay_exposes_preset_and_can_restore(self):
        self.command("apply_settings", settings={"max_speed": 20})
        failure = self.runtime.command({"command": "start", "track_id": "classic", "mode": "replay"})
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["compatible_settings"]["max_speed"], 18)
        restored = self.command("restore_compatible", track_id="classic")
        self.assertEqual(restored["mode"], "replay")
        self.assertEqual(restored["settings"]["max_speed"], 18)


class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = WorkspaceTemp()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)

    def test_settings_control_population_episode_and_experiment_destination(self):
        settings = ExperimentSettings(population=10, episode_steps=300)
        session = Session("monza", "red", 99, self.directory, settings=settings)
        self.assertEqual(len(session.agents), 10)
        self.assertEqual(session.seed, 7)
        for _ in range(300):
            if session.step():
                break
        self.assertEqual(session.generation, 2)
        paths = list((self.directory / "experiments").glob("*/monza.json"))
        self.assertEqual(len(paths), 1)
        self.assertIsNotNone(load_driver(paths[0]).experiment)

    def test_genuine_generation_and_champion_replay_for_both_circuits(self):
        runtime = importlib.import_module("runtime").Runtime(self.directory)
        runtime.command({"command": "apply_settings", "settings": {
            "population": 10, "episode_steps": 300}})
        for track_id in ("monza", "silverstone"):
            with self.subTest(track=track_id):
                started = runtime.command({"command": "start", "track_id": track_id,
                                           "mode": "train"})
                self.assertTrue(started["ok"])
                episode = started["snapshot"]["episode_id"]
                for _ in range(300):
                    runtime.step()
                    if runtime.snapshot()["generation"] == 2:
                        break
                self.assertEqual(runtime.snapshot()["generation"], 2)
                self.assertNotEqual(runtime.snapshot()["episode_id"], episode)
                saved = list((self.directory / "experiments").glob(f"*/{track_id}.json"))
                self.assertEqual(len(saved), 1)
                self.assertGreaterEqual(load_driver(saved[0]).fitness, 0)
                replay = runtime.command({"command": "start", "track_id": track_id,
                                          "mode": "replay"})
                self.assertTrue(replay["ok"], replay.get("error"))
                initial = replay["snapshot"]["cars"][0]["position"]
                runtime.step()
                self.assertNotEqual(runtime.snapshot()["cars"][0]["position"], initial)
                self.assertFalse(runtime.snapshot()["replay"]["transfer"])
                json.dumps(runtime.snapshot(), allow_nan=False)

    def test_training_randomness_is_independent_across_sessions_and_generations(self):
        settings = ExperimentSettings(population=10, episode_steps=300)
        a = Session("classic", save_dir=self.directory / "a", settings=settings)
        b = Session("classic", save_dir=self.directory / "b", settings=settings)
        for _ in range(310):
            self.assertEqual(a.step(), b.step())
        self.assertGreater(a.generation, 1)
        self.assertEqual([agent.car.position for agent in a.agents],
                         [agent.car.position for agent in b.agents])
        self.assertEqual([agent.network.activate([.1, .2, .3, .4, .5]) for agent in a.agents],
                         [agent.network.activate([.1, .2, .3, .4, .5]) for agent in b.agents])

    def test_same_track_with_wrong_settings_or_revision_cannot_block_saving(self):
        from models import experiment_metadata
        from tracks import load_track
        settings = ExperimentSettings(population=10, episode_steps=300)
        track = load_track("monza")
        metadata = experiment_metadata(track, settings)
        path = self.directory / "experiments" / metadata["fingerprint"] / "monza.json"
        driver = load_driver(ROOT / "demos" / "classic.json")
        for other in (ExperimentSettings(population=10, episode_steps=300, seed=9), None):
            wrong = experiment_metadata(track, other or settings)
            if other is None:
                wrong["geometry_revision"] = "old-revision"
                wrong["fingerprint"] = settings.fingerprint("monza", "old-revision", track.reward_version)
            save_driver(path, driver.network, "monza", 3, 1e9, 7, experiment=wrong)
            session = Session("monza", save_dir=self.directory, settings=settings)
            for _ in range(300):
                if session.step():
                    break
            self.assertEqual(load_driver(path).experiment, metadata)
            self.assertLess(load_driver(path).fitness, 1e9)

    def test_incompatible_saved_fitness_does_not_block_champion(self):
        from tracks import load_track
        settings = ExperimentSettings(population=10, episode_steps=300)
        track = load_track("monza")
        fingerprint = settings.fingerprint("monza", track.geometry_revision, track.reward_version)
        path = self.directory / "experiments" / fingerprint / "monza.json"
        driver = load_driver(ROOT / "demos" / "classic.json")
        save_driver(path, driver.network, "classic", 3, 1e9, 7)
        session = Session("monza", save_dir=self.directory, settings=settings)
        for _ in range(300):
            if session.step():
                break
        self.assertEqual(load_driver(path).track_id, "monza")
        self.assertLess(load_driver(path).fitness, 1e9)


if __name__ == "__main__":
    unittest.main()
