"""Arena skeleton (ROADMAP "before rung 1", strategy.md §9.1): play many hands and
report the average result with its margin of error.

One-player games only for now (e.g. blackjack against the dealer): the result of
a hand is `Game.utility` for the player. The margin is the half-width of a 95%
confidence interval: 1.96 x standard deviation / sqrt(hands).

Simulation goes through the engine (the rules as written), so comparing the
arena's average with an exact value checks the rules, the strategy and the arena
together.
"""

from __future__ import annotations

import math
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Callable

from .core import Engine
from .core.engine import Policy


@dataclass(frozen=True)
class SoloResult:
    hands: int
    total: float            # sum of results
    total_sq: float         # sum of squared results

    @property
    def mean(self) -> float:
        return self.total / self.hands

    @property
    def stdev(self) -> float:
        n = self.hands
        return math.sqrt(max(self.total_sq / n - self.mean ** 2, 0.0) * n / (n - 1))

    @property
    def margin(self) -> float:
        """Half-width of the 95% confidence interval of the mean."""
        return 1.96 * self.stdev / math.sqrt(self.hands)

    def merge(self, other: SoloResult) -> SoloResult:
        return SoloResult(self.hands + other.hands, self.total + other.total,
                          self.total_sq + other.total_sq)

    def __str__(self) -> str:
        return f"{self.mean:+.5f} +/- {self.margin:.5f} per hand over {self.hands:,} hands"


def play_solo(engine: Engine, policy: Policy, hands: int, seed: int = 0, player: int = 0) -> SoloResult:
    """Play `hands` independent hands (fresh shuffle each time)."""
    rng = random.Random(seed)
    total = total_sq = 0.0
    for _ in range(hands):
        trace = engine.play(rng, policy)
        x = float(engine.game.utility(engine.view(trace.final), player))
        total += x
        total_sq += x * x
    return SoloResult(hands, total, total_sq)


def play_solo_parallel(setup: Callable[[], tuple[Engine, Policy]], hands: int, seed: int = 0,
                       workers: int = 4, chunk: int = 50_000) -> SoloResult:
    """Same, split over processes. `setup` must be a picklable top-level function
    returning (engine, policy); chunk k uses seed (seed, k), so results are
    reproducible for a given chunk size."""
    sizes = [min(chunk, hands - start) for start in range(0, hands, chunk)]
    jobs = [(setup, n, seed * 1_000_003 + k) for k, n in enumerate(sizes)]
    result = SoloResult(0, 0.0, 0.0)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(_run_chunk, jobs):
            result = result.merge(part)
    return result


def _run_chunk(job) -> SoloResult:
    setup, n, seed = job
    engine, policy = setup()
    return play_solo(engine, policy, n, seed)
