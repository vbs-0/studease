"""Named random streams. All randomness flows from `random.Random` seeded by (seed, name), so adding a draw in
one area never shifts the numbers in another, and the same seed gives the same data on every machine."""
import random


def stream(seed: int, name: str) -> random.Random:
    return random.Random(f"{seed}:{name}")


def weighted(r: random.Random, options: list, weights: list[float]):
    return r.choices(options, weights=weights, k=1)[0]
