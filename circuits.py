"""Original editable GP circuit studies, independent of official artwork."""
from bisect import bisect_right
from functools import lru_cache
import json
import math
from pathlib import Path

import pygame

from progress import intersection_fraction
from simulator import Car, Track

DATA_DIR = Path(__file__).resolve().parent / 'assets' / 'circuits'
WORLD = (1920, 1080)
SUPPORTED_WIDTHS = (90, 120, 180)


def validate_centerline(points):
    if not isinstance(points, list) or len(points) < 5:
        raise ValueError('A centerline needs at least four closed segments')
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError('Each centerline point must have two coordinates')
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
            raise ValueError('Centerline coordinates must be finite normalized numbers')
    if points[0] != points[-1]:
        raise ValueError('Centerline must be explicitly closed')
    for a, b in zip(points, points[1:]):
        distance = math.dist(a, b)
        if distance <= 1e-9 or distance > .4:
            raise ValueError('Centerline has a disconnected or degenerate segment')
    _reject_intersections(points)


def _reject_intersections(points):
    segments = list(zip(points, points[1:]))
    for i, (a, b) in enumerate(segments):
        for j in range(i + 2, len(segments)):
            if i == 0 and j == len(segments) - 1:
                continue
            c, d = segments[j]
            if intersection_fraction(a, b, c, d) is not None or _segment_distance(a, b, c, d) < 1e-7:
                raise ValueError('Centerline intersects or touches a nonadjacent segment')


def _point_segment_distance(point, a, b):
    delta = (b[0] - a[0], b[1] - a[1])
    squared = sum(v * v for v in delta)
    t = max(0, min(1, sum((point[i] - a[i]) * delta[i] for i in (0, 1)) / squared))
    return math.dist(point, (a[0] + t * delta[0], a[1] + t * delta[1]))


def _segment_distance(a, b, c, d):
    if intersection_fraction(a, b, c, d) is not None:
        return 0
    return min(_point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
               _point_segment_distance(c, a, b), _point_segment_distance(d, a, b))


def _local_bend(segments, i, j, wrapped):
    if wrapped:
        i, j = j, i
        between = segments[i:] + segments[:j + 1]
    else:
        between = segments[i:j + 1]
    headings = [math.atan2(b[1] - a[1], b[0] - a[0]) for a, b in between]
    angle = headings[0]
    minimum = maximum = angle
    for previous, current in zip(headings, headings[1:]):
        angle += (current - previous + math.pi) % (2 * math.pi) - math.pi
        minimum, maximum = min(minimum, angle), max(maximum, angle)
    # Local joins and S-bends stay within an open half-plane of headings.
    if maximum - minimum < math.pi - 1e-7:
        return True
    # A tight turn can also bring disjoint segment ends into the same join
    # envelope. Return roads alongside each other overlap longitudinally;
    # they must satisfy full width clearance, even on a short closed loop.
    a, b = segments[i]
    c, d = segments[j]
    for start, end in ((a, b), (c, d)):
        axis = (end[0] - start[0], end[1] - start[1])
        first = sorted(sum(p[k] * axis[k] for k in (0, 1)) for p in (a, b))
        last = sorted(sum(p[k] * axis[k] for k in (0, 1)) for p in (c, d))
        if min(first[1], last[1]) - max(first[0], last[0]) <= 1e-7:
            return True
    return False


def validate_road(points, road_width):
    """Reject overlapping separate stretches, allowing the local bend envelope."""
    if isinstance(road_width, bool) or not isinstance(road_width, (int, float)) or not math.isfinite(road_width) or road_width <= 0:
        raise ValueError('Road width must be positive and finite')
    _reject_intersections(points)
    dense = []
    for a, b in zip(points, points[1:]):
        count = math.ceil(math.dist(a, b) / 24)
        dense.extend([(a[0] + (b[0] - a[0]) * i / count,
                       a[1] + (b[1] - a[1]) * i / count) for i in range(count)])
    points = dense + [dense[0]]
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    cumulative = [0]
    for length in lengths:
        cumulative.append(cumulative[-1] + length)
    total = cumulative[-1]
    segments = list(zip(points, points[1:]))
    for i, (a, b) in enumerate(segments):
        for j in range(i + 2, len(segments)):
            c, d = segments[j]
            if _segment_distance(a, b, c, d) >= road_width + 2:
                continue
            gap = (cumulative[j] + lengths[j] / 2) - (cumulative[i] + lengths[i] / 2)
            arc_gap = min(gap, total - gap)
            if arc_gap <= road_width * math.pi and _local_bend(segments, i, j, gap > total / 2):
                continue
            raise ValueError(f'Road width {road_width} merges nonadjacent stretches')


def _sample(points):
    # Fixed transform at the widest preset keeps world coordinates and browser
    # camera stable when the experiment changes only its road width.
    padding = 125
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    scale = min((WORLD[0] - padding * 2) / (max_x - min_x),
                (WORLD[1] - padding * 2) / (max_y - min_y))
    offset = ((WORLD[0] - (max_x - min_x) * scale) / 2,
              (WORLD[1] - (max_y - min_y) * scale) / 2)
    world = [(offset[0] + (x - min_x) * scale, offset[1] + (y - min_y) * scale) for x, y in points]
    samples = []
    for a, b in zip(world, world[1:]):
        count = math.ceil(math.dist(a, b) / 8)
        samples.extend([(a[0] + (b[0] - a[0]) * i / count,
                         a[1] + (b[1] - a[1]) * i / count) for i in range(count)])
    return samples + [samples[0]], world


def _gates(points, width):
    cumulative = [0]
    for a, b in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.dist(a, b))
    total = cumulative[-1]
    gates = []
    count = math.ceil(total / 140)
    for i in range(count):
        distance = total * i / count
        index = min(len(points) - 2, bisect_right(cumulative, distance) - 1)
        a, b = points[index:index + 2]
        length = math.dist(a, b)
        tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        fraction = (distance - cumulative[index]) / length
        center = (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)
        normal = (-tangent[1], tangent[0])
        gates.append(dict(center=center, tangent=tangent,
                          a=(center[0] + normal[0] * width / 2, center[1] + normal[1] * width / 2),
                          b=(center[0] - normal[0] * width / 2, center[1] - normal[1] * width / 2),
                          distance=distance))
    return gates


def circuit_catalog():
    result = []
    for path in sorted(DATA_DIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        result.append({key: data[key] for key in ('id', 'name', 'description', 'reference', 'direction', 'schematic_adjustments')}
                      | dict(group='Circuit studies', geometry_revision=str(data['revision']),
                             reward_version='checkpoints-1', supported_widths=list(SUPPORTED_WIDTHS)))
    return result


@lru_cache(maxsize=16)
def load_circuit(track_id: str, road_width: float = 120) -> Track:
    if track_id not in ('monza', 'silverstone'):
        raise ValueError(f'Unknown vector circuit: {track_id}')
    if isinstance(road_width, bool) or not isinstance(road_width, (int, float)) or not math.isfinite(road_width) or not 90 <= road_width <= 180:
        raise ValueError('Circuit road width must be between 90 and 180')
    data = json.loads((DATA_DIR / f'{track_id}.json').read_text(encoding='utf-8'))
    validate_centerline(data['centerline'])
    points, controls = _sample(data['centerline'])
    # Validation on moderately sampled geometry bounds construction cost while
    # retaining the original control corners and continuous finite segments.
    validate_road(controls, road_width)
    surface = pygame.Surface(WORLD)
    surface.fill((40, 67, 48))
    road_surface = pygame.Surface(WORLD)
    road_surface.fill('black')
    integer_points = [(round(x), round(y)) for x, y in points]
    for target, color in ((surface, (59, 62, 66)), (road_surface, 'white')):
        pygame.draw.lines(target, color, False, integer_points, round(road_width))
        for point in integer_points:
            pygame.draw.circle(target, color, point, round(road_width / 2))
    road_mask = pygame.mask.from_threshold(road_surface, (255, 255, 255), (1, 1, 1, 255))
    walls = road_mask.copy()
    walls.invert()
    gates = _gates(points, road_width)
    tangent = gates[0]['tangent']
    angle = math.degrees(math.atan2(-tangent[1], tangent[0])) % 360
    geometry = dict(centerline=points, gates=gates, road_width=road_width,
                    turns=[dict(number=turn['number'], name=turn['name'], position=controls[turn['point']]) for turn in data['turns']],
                    sectors=[dict(number=i + 1, position=controls[index]) for i, index in enumerate(data['sector_boundaries'])],
                    reference=data['reference'], direction=data['direction'], description=data['description'],
                    schematic_adjustments=data['schematic_adjustments'],
                    simulated_length=sum(math.dist(a, b) for a, b in zip(points, points[1:])))
    track = Track(surface, points[0], angle, track_id, geometry=geometry,
                  geometry_revision=str(data['revision']), reward_version='checkpoints-1', walls=walls)
    if Car(track).collides():
        raise ValueError('Circuit spawn footprint intersects a wall')
    return track
