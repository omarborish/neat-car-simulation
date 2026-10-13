"""Ordered, finite forward checkpoint crossings for schematic circuits."""
import math


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def intersection_fraction(a, b, c, d):
    """Return the fraction along AB at its finite intersection with CD."""
    movement = (b[0] - a[0], b[1] - a[1])
    gate = (d[0] - c[0], d[1] - c[1])
    denominator = cross(movement, gate)
    if abs(denominator) < 1e-9:
        return None
    offset = (c[0] - a[0], c[1] - a[1])
    t, u = cross(offset, gate) / denominator, cross(offset, movement) / denominator
    return t if 0 <= t <= 1 and 0 <= u <= 1 else None


class CheckpointProgress:
    def __init__(self, gates, road_width):
        if len(gates) < 3 or not math.isfinite(road_width) or road_width <= 0:
            raise ValueError('Progress needs at least three gates and a positive road width')
        self.gates = gates
        self.road_width = road_width
        self.next_gate = 1  # Gate zero is the finish; it comes last in each lap.
        self.laps = 0
        self.accepted = 0
        self.steps_since_progress = 0
        self.partial = 0.0

    @property
    def fitness(self):
        return 100 * self.accepted + self.partial

    def update(self, previous, current):
        self.steps_since_progress += 1
        movement = (current[0] - previous[0], current[1] - previous[1])
        crossings = []
        for index, gate in enumerate(self.gates):
            tangent, center = gate['tangent'], gate['center']
            forward = movement[0] * tangent[0] + movement[1] * tangent[1]
            before = sum((previous[i] - center[i]) * tangent[i] for i in (0, 1))
            after = sum((current[i] - center[i]) * tangent[i] for i in (0, 1))
            if forward <= 0 or before >= -1e-9 or after < -1e-9:
                continue
            fraction = intersection_fraction(previous, current, gate['a'], gate['b'])
            if fraction is not None:
                crossings.append((fraction, index))
        for _, index in sorted(crossings):
            if index != self.next_gate:
                continue
            self.accepted += 1
            self.partial = 0.0
            self.steps_since_progress = 0
            if index == 0:
                self.laps += 1
            self.next_gate = (index + 1) % len(self.gates)
        # A bounded best forward projection gives smooth feedback without
        # allowing repeated back-and-forth movement to accumulate reward.
        start = self.gates[(self.next_gate - 1) % len(self.gates)]['center']
        end = self.gates[self.next_gate]['center']
        segment = (end[0] - start[0], end[1] - start[1])
        length = math.hypot(*segment)
        if length and sum(movement[i] * segment[i] for i in (0, 1)) > 0:
            relative = (current[0] - start[0], current[1] - start[1])
            along = sum(relative[i] * segment[i] for i in (0, 1)) / length
            sideways = abs(cross(relative, segment)) / length
            if sideways <= self.road_width / 2:
                self.partial = max(self.partial, min(99.0, max(0.0, along / length * 99)))
