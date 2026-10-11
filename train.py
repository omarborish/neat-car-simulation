"""Prepare a driver ahead of a presentation without opening a window."""
import argparse
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from tracks import ROOT, TRACKS
from training import Session


def main():
    parser = argparse.ArgumentParser(description="Train NEAT drivers without a display")
    parser.add_argument("--track", choices=[spec.id for spec in TRACKS], default="classic")
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, default=ROOT / "saved")
    args = parser.parse_args()
    if args.generations < 1:
        parser.error("--generations must be at least 1")
    session = Session(args.track, seed=args.seed, save_dir=args.output)
    while session.generation <= args.generations:
        if session.step():
            print(f"Generation {session.generation - 1:03d}  "
                  f"best={session.last_generation_fitness:.1f}  "
                  f"session_best={session.best_fitness:.1f}", flush=True)
    print(f"Saved driver: {args.output / (args.track + '.json')}")


if __name__ == "__main__":
    main()
