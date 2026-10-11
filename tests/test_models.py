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
