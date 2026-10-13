"""Fixed-step driving model. Rendering size never changes the physics.

The five-ray sensor and four-action NEAT experiment follow the credited
NeuralNine / Cheesy AI tutorial. This implementation adds boundary checks,
bounded speed, movement substeps, and distance-based fitness.
"""
import math

import pygame

from settings import ExperimentSettings

CAR_LENGTH = 60
CAR_WIDTH = 30
SENSOR_RANGE = 300
SENSOR_ANGLES = (-90, -45, 0, 45, 90)
MAX_STEPS = 1200
PHYSICS_VERSION = 1
COLORS = ("mixed", "red", "green", "blue", "yellow", "orange", "pink", "purple")


class Track:
    def __init__(self, surface, start, angle, track_id, geometry=None,
                 geometry_revision="bitmap-1", reward_version="distance-1", walls=None):
        self.surface = surface
        self.start = start
        self.angle = angle
        self.id = track_id
        self.geometry = geometry
        self.geometry_revision = geometry_revision
        self.reward_version = reward_version
        self.width, self.height = surface.get_size()
        # The original tracks use white for walls. Include anti-aliased edges.
        self.walls = walls if walls is not None else pygame.mask.from_threshold(
            surface, (255, 255, 255), (18, 18, 18, 255))

    def is_wall(self, x, y):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        return bool(self.walls.get_at((int(x), int(y))))


class Car:
    def __init__(self, track, color="red", settings=None):
        self.settings = settings if settings is not None else ExperimentSettings()
        if not isinstance(self.settings, ExperimentSettings):
            raise ValueError("Car settings must be validated ExperimentSettings")
        self.track = track
        self.position = list(map(float, track.start))
        self.angle = track.angle
        self.speed = min(10.0, self.settings.max_speed)
        self.color = color
        self.alive = True
        self.distance = 0.0
        self.steps = 0
        self.radars = []
        self.progress = None
        if track.geometry is not None:
            from progress import CheckpointProgress
            self.progress = CheckpointProgress(track.geometry['gates'], track.geometry['road_width'])
        self.sense()

    @property
    def fitness(self):
        if self.progress is not None:
            return self.progress.fitness
        return self.distance / CAR_LENGTH

    def apply_action(self, action):
        if action == 0:
            self.angle = (self.angle + self.settings.steering_step) % 360
        elif action == 1:
            self.angle = (self.angle - self.settings.steering_step) % 360
        elif action == 2:
            self.speed = max(6.0, self.speed - 1)
        elif action == 3:
            self.speed = min(self.settings.max_speed, self.speed + 1)
        else:
            raise ValueError("A driving action must be 0, 1, 2, or 3")

    def collides(self):
        angle = math.radians(self.angle)
        dx, dy = math.cos(angle), -math.sin(angle)
        x, y = self.position
        # Check corners, side midpoints and center against the original bitmap.
        for forward, sideways in ((0, 0), (30, 15), (30, -15),
                                  (-30, 15), (-30, -15),
                                  (30, 0), (-30, 0), (0, 15), (0, -15)):
            if self.track.is_wall(x + dx * forward + dy * sideways,
                                  y + dy * forward - dx * sideways):
                return True
        return False

    def sense(self):
        x, y = self.position
        self.radars = []
        for offset in SENSOR_ANGLES:
            radians = math.radians(self.angle + offset)
            dx, dy = math.cos(radians), -math.sin(radians)
            distance = 0
            while distance < self.settings.sensor_range:
                if self.track.is_wall(x + dx * distance, y + dy * distance):
                    break
                distance = min(distance + 3, self.settings.sensor_range)
            self.radars.append(((x + dx * distance, y + dy * distance), distance))

    def inputs(self):
        return [distance / self.settings.sensor_range for _, distance in self.radars]

    def step(self, action):
        if not self.alive:
            return
        self.apply_action(action)
        previous = tuple(self.position)
        radians = math.radians(self.angle)
        substeps = max(1, math.ceil(self.speed / 4))
        stride = self.speed / substeps
        for _ in range(substeps):
            self.position[0] += math.cos(radians) * stride
            self.position[1] -= math.sin(radians) * stride
            if self.collides():
                self.alive = False
                break
            self.distance += stride
        self.steps += 1
        if self.progress is not None:
            self.progress.update(previous, tuple(self.position))
            if self.progress.steps_since_progress >= 600:
                self.alive = False
        self.sense()


def choose_action(network, car):
    outputs = network.activate(car.inputs())
    return max(range(4), key=outputs.__getitem__)
