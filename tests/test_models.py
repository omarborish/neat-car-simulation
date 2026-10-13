"""Saved drivers must preserve decisions and reject incompatible files."""
import importlib
import importlib.util
import json
from pathlib import Path
import unittest
from workspace_temp import WorkspaceTemp

import neat
from neat.activations import tanh_activation
from neat.aggregations import sum_aggregation


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("models"),
                             "Safe driver saving has not been implemented")
        self.models = importlib.import_module("models")
        self.folder = WorkspaceTemp()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "driver.json"
        self.network = neat.nn.FeedForwardNetwork(
            [-1, -2, -3, -4, -5], [0, 1, 2, 3],
            [(i, tanh_activation, sum_aggregation, i / 10, 1.0,
              [(-1, 0.5), (-3, -0.2)]) for i in range(4)])

    def save(self):
        self.models.save_driver(self.path, self.network, "classic", 3, 42.0, 7)

    def test_saved_network_makes_identical_decisions(self):
        self.save()
        driver = self.models.load_driver(self.path)
        inputs = [0.2, 0.4, 0.8, 0.4, 0.1]
        self.assertEqual(driver.network.activate(inputs), self.network.activate(inputs))
        self.assertEqual(driver.track_id, "classic")
        self.assertEqual(driver.generation, 3)
        self.assertTrue(hasattr(driver, "experiment"), "Driver needs experiment metadata")
        self.assertIsNone(driver.experiment)

    def experiment(self):
        # Literal metadata for the default experiment.
        return {"settings": {"max_speed": 18, "steering_step": 5, "sensor_range": 300,
                             "population": 30, "seed": 7, "episode_steps": 1200,
                             "road_width": 120},
                "geometry_revision": "bitmap-v1", "reward_version": "distance-v1"}

    def test_format_two_round_trip_keeps_decisions_and_metadata(self):
        self.assertIsNotNone(importlib.util.find_spec("settings"), "Settings are missing")
        settings = importlib.import_module("settings").ExperimentSettings()
        experiment = self.experiment()
        experiment["fingerprint"] = settings.fingerprint("classic", "bitmap-v1", "distance-v1")
        self.models.save_driver(self.path, self.network, "classic", 3, 42.0, 7,
                                experiment=experiment)
        self.assertEqual(json.loads(self.path.read_text())["format_version"], 2)
        driver = self.models.load_driver(self.path)
        self.assertEqual(driver.experiment, experiment)
        inputs = [0.2, 0.4, 0.8, 0.4, 0.1]
        self.assertEqual(driver.network.activate(inputs), self.network.activate(inputs))

    def test_invalid_experiment_is_rejected_on_save(self):
        settings = importlib.import_module("settings").ExperimentSettings()
        for updates in ({"geometry_revision": ""}, {"reward_version": True},
                        {"settings": {**settings.to_dict(), "population": 9}},
                        {"settings": {"population": 30}}, {"fingerprint": "forged"},
                        {"extra": "unknown"}):
            experiment = self.experiment()
            experiment["fingerprint"] = settings.fingerprint("classic", "bitmap-v1", "distance-v1")
            experiment.update(updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.models.save_driver(self.path, self.network, "classic", 3, 42.0, 7,
                                        experiment=experiment)
            self.assertFalse(self.path.exists(), "Invalid metadata must not create a save")

    def test_tampered_experiment_is_rejected_on_load(self):
        settings = importlib.import_module("settings").ExperimentSettings()
        self.save()
        data = json.loads(self.path.read_text())
        data["format_version"] = 2
        data["experiment"] = self.experiment()
        data["experiment"]["fingerprint"] = settings.fingerprint("classic", "bitmap-v1", "distance-v1")
        for key, value in (("fingerprint", "forged"), ("geometry_revision", "bitmap-v2"),
                           ("reward_version", "distance-v2")):
            tampered = json.loads(json.dumps(data))
            tampered["experiment"][key] = value
            self.path.write_text(json.dumps(tampered))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "fingerprint"):
                self.models.load_driver(self.path)

    def test_format_two_supports_track_metadata_for_later_transfer(self):
        self.assertIsNotNone(importlib.util.find_spec("settings"), "Settings are missing")
        settings = importlib.import_module("settings").ExperimentSettings()
        experiment = self.experiment()
        experiment["fingerprint"] = settings.fingerprint("monza", "bitmap-v1", "distance-v1")
        self.models.save_driver(self.path, self.network, "monza", 3, 42.0, 7,
                                experiment=experiment)
        driver = self.models.load_driver(self.path)
        self.assertEqual(driver.track_id, "monza")
        self.assertEqual(driver.experiment, experiment)

    def test_wrong_physics_version_is_rejected(self):
        self.save()
        data = json.loads(self.path.read_text())
        data["physics_version"] = 999
        self.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "physics"):
            self.models.load_driver(self.path)

    def test_non_finite_network_weight_is_rejected(self):
        self.save()
        data = json.loads(self.path.read_text())
        data["nodes"][0]["links"][0][1] = float("nan")
        self.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.models.load_driver(self.path)

    def test_invalid_json_reports_a_readable_error(self):
        self.path.write_text("not a driver")
        with self.assertRaisesRegex(ValueError, "driver"):
            self.models.load_driver(self.path)

    def test_unknown_activation_is_rejected(self):
        self.save()
        data = json.loads(self.path.read_text())
        data["nodes"][0]["activation"] = "unknown"
        self.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.models.load_driver(self.path)


if __name__ == "__main__":
    unittest.main()
