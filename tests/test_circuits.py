import importlib
import importlib.util
import math
import unittest
import pygame
from simulator import Car
from tracks import load_track


class CircuitTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('circuits'), 'Vector circuits are missing')
        self.circuits = importlib.import_module('circuits')

    def test_each_width_has_closed_finite_geometry_and_clear_spawn(self):
        for circuit in ('monza', 'silverstone'):
            for width in (90, 120, 180):
                with self.subTest(circuit=circuit, width=width):
                    track = load_track(circuit, road_width=width)
                    points = track.geometry['centerline']
                    self.assertEqual(points[0], points[-1])
                    self.assertTrue(all(math.isfinite(v) for p in points for v in p))
                    self.assertEqual(track.surface.get_size(), (1920, 1080))
                    self.assertFalse(Car(track).collides())
                    car = Car(track)
                    car.step(3)
                    self.assertTrue(car.alive)
                    self.assertEqual(len(track.geometry['sectors']), 3)
                    self.assertEqual(len(track.geometry['turns']), 11 if circuit == 'monza' else 18)
                    self.assertTrue(track.geometry['reference']['source_url'].startswith('https://www.formula1.com/'))
                    self.assertEqual(track.geometry_revision, '1')
                    self.assertEqual(track.reward_version, 'checkpoints-1')

    def test_decoration_cannot_change_drivable_geometry(self):
        track = load_track('monza')
        clear = track.start
        self.assertFalse(track.is_wall(*clear))
        self.assertTrue(track.is_wall(0, 0))
        original = track.surface.copy()
        try:
            track.surface.fill('white')
            self.assertFalse(track.is_wall(*clear))
            track.surface.fill('black')
            self.assertTrue(track.is_wall(0, 0))
        finally:
            track.surface.blit(original, (0, 0))

    def test_rejects_malformed_open_disconnected_or_crossing_centerlines(self):
        bad = [[], [[0, 0], [1, 0], [1, 1]],
               [[0, 0], [float('nan'), 0], [.1, .1], [0, .1], [0, 0]],
               [[0, 0], ['bad', 0], [.1, .1], [0, .1], [0, 0]],
               [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
               [[.1, .1], [.4, .4], [.1, .4], [.4, .1], [.1, .1]]]
        for points in bad:
            with self.subTest(points=points):
                with self.assertRaises(ValueError):
                    self.circuits.validate_centerline(points)

    def test_rejects_neighboring_road_overlap(self):
        # Two long parallel stretches only 50 units apart merge at width 90.
        points = [(100, 100), (700, 100), (700, 150), (100, 150), (100, 100)]
        with self.assertRaises(ValueError):
            self.circuits.validate_road(points, 90)

    def test_short_parallel_roads_are_not_exempted_as_a_local_bend(self):
        points = [(100, 100), (300, 100), (300, 150), (100, 150), (100, 100)]
        for ordered in (points, list(reversed(points))):
            with self.subTest(direction=ordered):
                with self.assertRaises(ValueError):
                    self.circuits.validate_road(ordered, 90)

    def test_original_bitmap_fitness_stays_distance_based(self):
        car = Car(load_track('classic'))
        car.step(3)
        self.assertAlmostEqual(car.fitness, car.distance / 60)
        self.assertIsNone(car.track.geometry)

    def test_catalog_exposes_only_supported_vector_presets(self):
        catalog = self.circuits.circuit_catalog()
        self.assertEqual({item['id'] for item in catalog}, {'monza', 'silverstone'})
        for item in catalog:
            self.assertEqual(item['supported_widths'], [90, 120, 180])
            self.assertIn('schematic', item['description'].lower())

    def test_the_rendered_centerline_is_one_connected_drivable_road(self):
        for circuit in ('monza', 'silverstone'):
            for width in (90, 120, 180):
                track = load_track(circuit, width)
                points = track.geometry['centerline']
                self.assertTrue(all(not track.is_wall(*point) for point in points))
                road = track.walls.copy()
                road.invert()
                self.assertEqual(len(road.connected_components()), 1)

    def test_car_footprint_fits_along_straights_and_corner_samples(self):
        for circuit in ('monza', 'silverstone'):
            for width in (90, 120, 180):
                track = load_track(circuit, width)
                car = Car(track)
                points = track.geometry['centerline']
                for a, b in zip(points, points[1:]):
                    car.position = list(a)
                    car.angle = math.degrees(math.atan2(a[1] - b[1], b[0] - a[0]))
                    self.assertFalse(car.collides(), (circuit, width, a))

    def test_invalid_widths_and_unknown_circuits_are_rejected(self):
        for width in (0, 89, 181, float('nan'), True, '120'):
            with self.assertRaises(ValueError):
                self.circuits.load_circuit('monza', width)
        with self.assertRaises(ValueError):
            self.circuits.load_circuit('bahrain')

if __name__ == '__main__':
    unittest.main()
