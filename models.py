"""Export only the feed-forward driver's numeric data, in readable JSON."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import neat
from neat.activations import tanh_activation
from neat.aggregations import sum_aggregation

from simulator import PHYSICS_VERSION


@dataclass
class Driver:
    network: object
    track_id: str
    generation: int
    fitness: float
    seed: int


def save_driver(path, network, track_id, generation, fitness, seed):
    nodes = []
    for key, activation, aggregation, bias, response, links in network.node_evals:
        if activation is not tanh_activation or aggregation is not sum_aggregation:
            raise ValueError("This experiment saves tanh / sum networks only")
        nodes.append({"id": key, "activation": "tanh", "aggregation": "sum",
                      "bias": bias, "response": response, "links": links})
    data = {
        "format_version": 1, "physics_version": PHYSICS_VERSION,
        "track_id": track_id, "generation": generation, "fitness": fitness,
        "seed": seed, "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": network.input_nodes, "outputs": network.output_nodes,
        "nodes": nodes,
    }
    content = json.dumps(data, indent=2, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Saved driver contains an invalid number")
    return value


def load_driver(path):
    try:
        path = Path(path)
        if path.stat().st_size > 1_000_000:
            raise ValueError("Saved driver is too large")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["format_version"] != 1:
            raise ValueError("Unsupported saved driver format")
        if data["physics_version"] != PHYSICS_VERSION:
            raise ValueError("Saved driver uses a different physics version")
        if data["inputs"] != [-1, -2, -3, -4, -5] or data["outputs"] != [0, 1, 2, 3]:
            raise ValueError("Saved driver needs five sensors and four actions")
        from tracks import get_spec
        get_spec(data["track_id"])
        if not isinstance(data["nodes"], list) or len(data["nodes"]) > 1000:
            raise ValueError("Invalid saved driver nodes")
        seen = set(data["inputs"])
        evaluations = []
        for node in data["nodes"]:
            key = node["id"]
            if type(key) is not int or key < 0 or key in seen:
                raise ValueError("Invalid saved driver node ID")
            if node["activation"] != "tanh" or node["aggregation"] != "sum":
                raise ValueError("Unsupported saved driver activation")
            if not isinstance(node["links"], list) or len(node["links"]) > 1000:
                raise ValueError("Invalid saved driver links")
            links = []
            for source, weight in node["links"]:
                if type(source) is not int or source not in seen:
                    raise ValueError("Saved driver is not a feed-forward network")
                links.append((source, _number(weight)))
            evaluations.append((key, tanh_activation, sum_aggregation,
                                _number(node["bias"]), _number(node["response"]), links))
            seen.add(key)
        generation, seed = data["generation"], data["seed"]
        if type(generation) is not int or generation < 1 or type(seed) is not int:
            raise ValueError("Invalid saved driver training details")
        return Driver(neat.nn.FeedForwardNetwork(data["inputs"], data["outputs"], evaluations),
                      data["track_id"], generation, _number(data["fitness"]), seed)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read saved driver: {error}") from error
