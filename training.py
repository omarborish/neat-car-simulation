"""NEAT generations evaluated one simulation step at a time for responsive UI."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import random

import neat

from models import compatible_driver, experiment_metadata, load_driver, save_driver
from settings import ExperimentSettings
from simulator import Car, MAX_STEPS, choose_action
from tracks import ROOT, load_track

CAR_COLORS = ("red", "green", "blue", "yellow", "orange", "pink", "purple")


@dataclass
class Agent:
    genome: object
    network: object
    car: Car


class Session:
    def __init__(self, track_id, color="mixed", seed=7, save_dir=None, settings=None):
        if settings is not None and not isinstance(settings, ExperimentSettings):
            raise ValueError("Session settings must be validated ExperimentSettings")
        self.settings = settings
        effective = settings if settings is not None else ExperimentSettings()
        self.track = load_track(track_id, effective.road_width)
        self.color = color
        self.seed = effective.seed if settings is not None else seed
        self.save_dir = Path(save_dir) if save_dir is not None else ROOT / "saved"
        self.experiment = experiment_metadata(self.track, effective) if settings is not None else None
        if self.experiment is not None:
            self.save_dir = self.save_dir / "experiments" / self.experiment["fingerprint"]
        self.save_path = self.save_dir / f"{track_id}.json"
        self.episode_steps = effective.episode_steps if settings is not None else MAX_STEPS
        self.config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                  neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                  str(ROOT / "config.txt"))
        if settings is not None:
            self.config.pop_size = settings.population
        previous_random = random.getstate()
        try:
            random.seed(self.seed)
            self.population = neat.Population(self.config)
            self.random_state = random.getstate()
        finally:
            random.setstate(previous_random)
        self.best_fitness = 0.0
        self.best_network = None
        self.saved_fitness = float("-inf") if settings is not None else 0.0
        saved = self.save_path
        if saved.is_file():
            try:
                driver = load_driver(saved)
                if (settings is None and driver.track_id == track_id
                        and driver.experiment is None) or (settings is not None
                        and compatible_driver(driver, self.track, settings)):
                    self.saved_fitness = driver.fitness
            except ValueError:
                pass  # A new completed generation replaces an unreadable local save.
        self.last_generation_fitness = 0.0
        self.start_generation()

    @property
    def generation(self):
        return self.population.generation + 1

    @property
    def alive(self):
        return sum(agent.car.alive for agent in self.agents)

    def start_generation(self):
        self.ticks = 0
        self.agents = []
        self.population.reporters.start_generation(self.population.generation)
        for index, genome in enumerate(self.population.population.values()):
            genome.fitness = 0.0
            color = CAR_COLORS[index % len(CAR_COLORS)] if self.color == "mixed" else self.color
            self.agents.append(Agent(genome,
                neat.nn.FeedForwardNetwork.create(genome, self.config),
                Car(self.track, color, self.settings)))

    def set_color(self, color):
        self.color = color
        for index, agent in enumerate(self.agents):
            agent.car.color = CAR_COLORS[index % len(CAR_COLORS)] if color == "mixed" else color

    def step(self):
        for agent in self.agents:
            if agent.car.alive:
                agent.car.step(choose_action(agent.network, agent.car))
                agent.genome.fitness = agent.car.fitness
        self.ticks += 1
        if not self.alive or self.ticks >= self.episode_steps:
            self.finish_generation()
            self.start_generation()
            return True
        return False

    def finish_generation(self):
        population = self.population
        best = max(self.agents, key=lambda agent: agent.genome.fitness)
        self.last_generation_fitness = best.genome.fitness
        population.reporters.post_evaluate(self.config, population.population,
                                          population.species, best.genome)
        if best.genome.fitness > self.best_fitness:
            self.best_fitness = best.genome.fitness
            self.best_network = best.network
            population.best_genome = deepcopy(best.genome)
        if best.genome.fitness > self.saved_fitness:
            save_driver(self.save_path, best.network, self.track.id, self.generation,
                        best.genome.fitness, self.seed, experiment=self.experiment)
            self.saved_fitness = best.genome.fitness
        # This is the reproduction/speciation lifecycle from neat-python 0.92.
        previous_random = random.getstate()
        try:
            random.setstate(self.random_state)
            population.population = population.reproduction.reproduce(
                self.config, population.species, self.config.pop_size, population.generation)
            if not population.species.species:
                population.reporters.complete_extinction()
                population.population = population.reproduction.create_new(
                    self.config.genome_type, self.config.genome_config, self.config.pop_size)
            population.species.speciate(self.config, population.population, population.generation)
            self.random_state = random.getstate()
        finally:
            random.setstate(previous_random)
        population.reporters.end_generation(self.config, population.population, population.species)
        population.generation += 1
