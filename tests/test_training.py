"""Exercise actual NEAT evaluation, champion export and replay."""
import importlib
import importlib.util
from pathlib import Path
import unittest
from workspace_temp import WorkspaceTemp

from simulator import Car
from tracks import load_track


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("training"),
                             "Training sessions have not been implemented")
        self.training = importlib.import_module("training")
        self.folder = WorkspaceTemp()
        self.addCleanup(self.folder.cleanup)

    def test_generation_finishes_and_saved_car_replays(self):
        session = self.training.Session("classic", seed=7,
                                        save_dir=Path(self.folder.name))
        first_generation = session.generation
        for _ in range(1201):
            session.step()
            if session.generation > first_generation:
                break
        self.assertEqual(session.generation, first_generation + 1)
        path = Path(self.folder.name) / "classic.json"
        self.assertTrue(path.is_file())
        from models import load_driver
        from simulator import choose_action
        driver = load_driver(path)
        car = Car(load_track("classic"))
        for _ in range(20):
            car.step(choose_action(driver.network, car))
        self.assertGreater(car.distance, 0)

    def test_restart_is_deterministic_for_same_seed(self):
        a = self.training.Session("classic", seed=7,
                                  save_dir=Path(self.folder.name) / "a")
        for _ in range(10):
            a.step()
        positions = [tuple(agent.car.position) for agent in a.agents]
        b = self.training.Session("classic", seed=7,
                                  save_dir=Path(self.folder.name) / "b")
        for _ in range(10):
            b.step()
        self.assertEqual([tuple(agent.car.position) for agent in b.agents], positions)


if __name__ == "__main__":
    unittest.main()
