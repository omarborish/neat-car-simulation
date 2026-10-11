"""Regression checks for track boundaries, car state, and safe starts."""
import importlib
import importlib.util
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("simulator"),
                             "The simulation API has not been implemented")
        self.sim = importlib.import_module("simulator")

    def road(self):
        surface = pygame.Surface((600, 400))
        surface.fill("black")
        return self.sim.Track(surface, (300, 200), 0, "test")

    def test_off_image_positions_are_walls(self):
        track = self.road()
        for point in [(-1, 100), (600, 100), (100, -1), (100, 400)]:
            self.assertTrue(track.is_wall(*point), point)
        self.assertFalse(track.is_wall(300, 200))

    def test_white_area_is_a_wall(self):
        track = self.road()
        track.surface.fill("white", (350, 0, 40, 400))
        track = self.sim.Track(track.surface, (300, 200), 0, "test")
        self.assertTrue(track.is_wall(360, 200))

    def test_radar_stops_at_image_edge_without_crashing(self):
        car = self.sim.Car(self.road())
        car.position = [580.0, 200.0]
        car.sense()
        self.assertEqual(len(car.inputs()), 5)
        self.assertAlmostEqual(car.radars[2][1], 20, delta=2)
        self.assertTrue(all(0 <= value <= 1 for value in car.inputs()))

    def test_acceleration_and_braking_have_limits(self):
        car = self.sim.Car(self.road())
        for _ in range(100):
            car.apply_action(3)
        self.assertEqual(car.speed, 18)
        for _ in range(100):
            car.apply_action(2)
        self.assertEqual(car.speed, 6)

    def test_distance_reward_is_not_accumulated_again_each_frame(self):
        car = self.sim.Car(self.road())
        car.step(3)
        first = car.fitness
        car.step(3)
        self.assertAlmostEqual(car.fitness, car.distance / 60)
        self.assertGreater(car.fitness, first)

    def test_dead_car_does_not_move_or_revive(self):
        car = self.sim.Car(self.road())
        car.alive = False
        before = tuple(car.position)
        car.step(3)
        self.assertFalse(car.alive)
        self.assertEqual(tuple(car.position), before)

    def test_color_is_visual_only(self):
        car = self.sim.Car(self.road(), color="red")
        before = (tuple(car.position), car.speed, car.fitness)
        car.color = "blue"
        self.assertEqual((tuple(car.position), car.speed, car.fitness), before)

    def test_each_supplied_track_has_a_clear_start_and_five_sensors(self):
        tracks = importlib.import_module("tracks")
        self.assertEqual(len(tracks.TRACKS), 11)
        for spec in tracks.TRACKS:
            with self.subTest(track=spec.id):
                track = tracks.load_track(spec.id)
                car = self.sim.Car(track)
                self.assertFalse(car.collides(), "Car starts inside a wall")
                car.sense()
                self.assertEqual(len(car.inputs()), 5)
                car.step(3)
                self.assertTrue(car.alive, "Start direction immediately hits a wall")


if __name__ == "__main__":
    unittest.main()
