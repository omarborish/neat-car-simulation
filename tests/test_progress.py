import importlib
import importlib.util
import unittest


def gate(center, tangent, a, b):
    return dict(center=center, tangent=tangent, a=a, b=b)


def loop():
    return [gate((0, 50), (0, -1), (-10, 50), (10, 50)),
            gate((50, 0), (1, 0), (50, -10), (50, 10)),
            gate((100, 50), (0, 1), (90, 50), (110, 50)),
            gate((50, 100), (-1, 0), (50, 90), (50, 110))]


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('progress'), 'Ordered progress is missing')
        self.progress = importlib.import_module('progress').CheckpointProgress(loop(), 20)

    def test_full_forward_sequence_completes_one_lap(self):
        for previous, current in [((40, 0), (60, 0)), ((100, 40), (100, 60)),
                                  ((60, 100), (40, 100)), ((0, 60), (0, 40))]:
            self.progress.update(previous, current)
        self.assertEqual(self.progress.laps, 1)
        self.assertGreaterEqual(self.progress.fitness, 400)
        self.assertLess(self.progress.fitness, 500)
        self.assertEqual(self.progress.steps_since_progress, 0)

    def test_finish_first_reverse_and_outside_finite_gate_do_not_score(self):
        for previous, current in [((0, 60), (0, 40)), ((60, 0), (40, 0)),
                                  ((40, 40), (60, 40)), ((100, 40), (100, 60))]:
            self.progress.update(previous, current)
        self.assertEqual(self.progress.laps, 0)
        self.assertLess(self.progress.fitness, 100)
        self.assertEqual(self.progress.steps_since_progress, 4)

    def test_repeated_gate_and_two_gate_circling_cannot_complete_lap(self):
        self.progress.update((40, 0), (60, 0))
        self.progress.update((100, 40), (100, 60))
        for _ in range(10):
            self.progress.update((60, 0), (40, 0))
            self.progress.update((40, 0), (60, 0))
            self.progress.update((100, 60), (100, 40))
            self.progress.update((100, 40), (100, 60))
        self.assertEqual(self.progress.laps, 0)
        self.assertGreaterEqual(self.progress.fitness, 200)
        self.assertLess(self.progress.fitness, 300)
        self.assertEqual(self.progress.steps_since_progress, 40)

    def test_partial_progress_is_bounded_and_ignores_reverse_motion(self):
        self.progress.update((0, 50), (20, 30))
        self.assertGreater(self.progress.fitness, 0)
        first = self.progress.fitness
        self.progress.update((20, 30), (10, 40))
        self.assertEqual(self.progress.fitness, first)
        self.progress.update((10, 40), (10000, -9950))
        self.assertLess(self.progress.fitness, 200)

    def test_vector_car_stops_after_600_steps_without_a_gate(self):
        from tracks import load_track
        from simulator import Car
        car = Car(load_track('monza'))
        car.speed = 0
        for _ in range(599):
            car.step(0)
        self.assertTrue(car.alive)
        car.step(0)
        self.assertFalse(car.alive)
        self.assertEqual(car.progress.steps_since_progress, 600)

    def test_a_trip_along_each_authored_centerline_accepts_exactly_one_lap(self):
        from tracks import load_track
        for name in ('monza', 'silverstone'):
            track = load_track(name)
            progress = importlib.import_module('progress').CheckpointProgress(
                track.geometry['gates'], track.geometry['road_width'])
            points = track.geometry['centerline']
            for previous, current in zip(points, points[1:]):
                progress.update(previous, current)
            self.assertEqual(progress.laps, 1, name)
            self.assertEqual(progress.accepted, len(track.geometry['gates']), name)

if __name__ == '__main__':
    unittest.main()
