"""The shipped driver must survive and cover the circuit, not circle in place."""
import unittest

from models import load_driver
from simulator import Car, choose_action
from tracks import ROOT, load_track


class BundledDemoTests(unittest.TestCase):
    def test_bundled_classic_driver_survives_full_episode_and_covers_circuit(self):
        driver = load_driver(ROOT / "demos" / "classic.json")
        car = Car(load_track("classic"))
        positions = []
        for _ in range(1200):
            car.step(choose_action(driver.network, car))
            positions.append(tuple(car.position))
        self.assertTrue(car.alive)
        self.assertEqual(car.steps, 1200)
        self.assertAlmostEqual(car.fitness, 359.5, delta=0.1)
        self.assertLess(min(x for x, _ in positions), 400)
        self.assertGreater(max(x for x, _ in positions), 1500)
        self.assertLess(min(y for _, y in positions), 300)
        self.assertGreater(max(y for _, y in positions), 800)


if __name__ == "__main__":
    unittest.main()
