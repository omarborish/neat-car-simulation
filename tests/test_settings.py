"""Validated experiments must preserve defaults and bound browser inputs."""
import importlib
import importlib.util
import json
from pathlib import Path
import unittest

import pygame

from simulator import Car, Track


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("settings"),
                             "Experiment settings have not been implemented")
        self.Settings = importlib.import_module("settings").ExperimentSettings

    def test_defaults_round_trip(self):
        expected = {"max_speed": 18, "steering_step": 5, "sensor_range": 300,
                    "population": 30, "seed": 7, "episode_steps": 1200,
                    "road_width": 120}
        self.assertEqual(self.Settings().to_dict(), expected)
        self.assertEqual(self.Settings.from_dict(expected), self.Settings())

    def test_invalid_settings_are_rejected(self):
        invalid = [{"unknown": 1}, [], None]
        for field in ("max_speed", "steering_step", "sensor_range", "population",
                      "seed", "episode_steps", "road_width"):
            invalid.extend({field: value} for value in
                           (True, False, float("nan"), float("inf"), "12"))
        invalid.extend({field: value} for field, values in {
            "max_speed": (5, 25), "steering_step": (0, 11),
            "sensor_range": (99, 601), "population": (9, 101, 30.5),
            "seed": (-1, 2147483648, 7.5),
            "episode_steps": (299, 3601, 1200.5), "road_width": (89, 181),
        }.items() for value in values)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.Settings.from_dict(data)

    def test_range_endpoints_are_accepted(self):
        for data in (
            {"max_speed": 6, "steering_step": 1, "sensor_range": 100,
             "population": 10, "seed": 0, "episode_steps": 300, "road_width": 90},
            {"max_speed": 24, "steering_step": 10, "sensor_range": 600,
             "population": 100, "seed": 2147483647, "episode_steps": 3600,
             "road_width": 180},
        ):
            self.assertEqual(self.Settings.from_dict(data).to_dict(), data)

    def test_fingerprint_is_canonical_and_tracks_experiment_identity(self):
        settings = self.Settings()
        original = settings.fingerprint("classic", "bitmap-v1", "distance-v1")
        reversed_fields = dict(reversed(list(settings.to_dict().items())))
        self.assertEqual(original, self.Settings.from_dict(reversed_fields).fingerprint(
            "classic", "bitmap-v1", "distance-v1"))
        self.assertEqual(original, self.Settings(max_speed=18.0).fingerprint(
            "classic", "bitmap-v1", "distance-v1"))
        self.assertEqual(len(original), 64)
        for args in (("track02", "bitmap-v1", "distance-v1"),
                     ("classic", "bitmap-v2", "distance-v1"),
                     ("classic", "bitmap-v1", "distance-v2")):
            self.assertNotEqual(original, settings.fingerprint(*args))
        for field, value in (("max_speed", 12), ("population", 40),
                             ("road_width", 150), ("seed", 9), ("episode_steps", 600)):
            self.assertNotEqual(original, self.Settings.from_dict({field: value}).fingerprint(
                "classic", "bitmap-v1", "distance-v1"))

    def test_car_consumes_physics_settings_and_color_is_visual(self):
        surface = pygame.Surface((1600, 1600))
        surface.fill("black")
        track = Track(surface, (800, 800), 0, "test")
        settings = self.Settings(max_speed=8, steering_step=2, sensor_range=100)
        car = Car(track, "red", settings=settings)
        self.assertEqual(car.speed, 8)
        self.assertEqual(car.inputs(), [1, 1, 1, 1, 1])
        self.assertEqual([distance for _, distance in car.radars], [100] * 5)
        car.apply_action(0)
        self.assertEqual(car.angle, 2)
        car.apply_action(1)
        self.assertEqual(car.angle, 0)
        for _ in range(100):
            car.apply_action(3)
        self.assertEqual(car.speed, 8)
        for _ in range(100):
            car.apply_action(2)
        self.assertEqual(car.speed, 6)
        fingerprint = car.settings.fingerprint("test", "v1", "v1")
        car.color = "blue"
        self.assertEqual(car.settings.fingerprint("test", "v1", "v1"), fingerprint)

    def test_explicit_defaults_preserve_car_actions_sensors_and_collisions(self):
        # Literal trace generated from the pre-browser implementation, not
        # another instance of today's Car. Keep the long bundled-driver oracle.
        fixture = json.loads((Path(__file__).parent / 'fixtures' / 'native-default-trace.json').read_text())
        surface = pygame.Surface((600, 400))
        surface.fill("black")
        surface.fill("white", (430, 0, 40, 400))
        track = Track(surface, (300, 200), 0, "test")
        for car in (Car(track), Car(track, settings=self.Settings())):
            for row in fixture['trace']:
                car.step(row['action'])
                self.assertEqual([round(v, 9) for v in car.position], row['position'])
                self.assertEqual(json.loads(json.dumps(car.radars)), row['radars'])
                self.assertEqual(car.inputs(), row['inputs'])
                self.assertEqual(car.angle, row['angle'])
                self.assertEqual(car.speed, row['speed'])
                self.assertEqual(car.alive, row['alive'])
                self.assertEqual(car.collides(), row['collides'])
                self.assertEqual(round(car.fitness, 9), row['fitness'])
