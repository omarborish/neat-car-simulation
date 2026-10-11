"""NEAT generations evaluated one simulation step at a time for responsive UI."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import random

import neat

from models import load_driver, save_driver
from simulator import Car, MAX_STEPS, choose_action
from tracks import ROOT, load_track

CAR_COLORS = ("red", "green", "blue", "yellow", "orange", "pink", "purple")


@dataclass
class Agent:
    genome: object
    network: object
    car: Car


class Session:
    def __init__(self, track_id, color="mixed", seed=7, save_dir=None):
        self.track = load_track(track_id)
        self.color = color
        self.seed = seed
        self.save_dir = Path(save_dir) if save_dir is not None else ROOT / "saved"
        self.config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                  neat.DefaultSpeciesSet, neat.DefaultStagnation,
                                  str(ROOT / "config.txt"))
        random.seed(seed)
        self.population = neat.Population(self.config)
        self.best_fitness = 0.0
        self.best_network = None
        self.saved_fitness = 0.0
        saved = self.save_dir / f"{track_id}.json"
        if saved.is_file():
            try:
                self.saved_fitness = load_driver(saved).fitness
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
                neat.nn.FeedForwardNetwork.create(genome, self.config), Car(self.track, color)))

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
        if not self.alive or self.ticks >= MAX_STEPS:
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
            save_driver(self.save_dir / f"{self.track.id}.json", best.network,
                        self.track.id, self.generation, best.genome.fitness, self.seed)
            self.saved_fitness = best.genome.fitness
        # This is the reproduction/speciation lifecycle from neat-python 0.92.
        population.population = population.reproduction.reproduce(
            self.config, population.species, self.config.pop_size, population.generation)
        if not population.species.species:
            population.reporters.complete_extinction()
            population.population = population.reproduction.create_new(
                self.config.genome_type, self.config.genome_config, self.config.pop_size)
        population.species.speciate(self.config, population.population, population.generation)
        population.reporters.end_generation(self.config, population.population, population.species)
        population.generation += 1
