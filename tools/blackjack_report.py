"""Blackjack rung report: house edges, basic strategy charts, and the Monte Carlo
check of the arena against exact values.

    python -m tools.blackjack_report                 # exact values and charts (~1 min)
    python -m tools.blackjack_report --hands 10000000 --workers 20   # + Monte Carlo
"""

from __future__ import annotations

import argparse
import time

from joker.arena import play_solo_parallel
from joker.core import Engine
from joker.games.blackjack import Blackjack, BlackjackRules
from joker.strategy.blackjack import (BlackjackSolver, basic_strategy_chart, engine_policy,
                                      format_chart, solver_policy)

EXACT = {
    "infinite deck, S17, DAS, split to 4": BlackjackRules(decks=None, max_hands=4),
    "infinite deck, H17, DAS, split to 4": BlackjackRules(decks=None, hit_soft_17=True, max_hands=4),
    "1 deck, S17, no splitting": BlackjackRules(decks=1, max_hands=1),
    "1 deck, S17, no DAS, split once": BlackjackRules(decks=1, max_hands=2, double_after_split=False),
    "1 deck, S17, DAS, split once": BlackjackRules(decks=1, max_hands=2),
    "6 decks, S17, DAS, split once": BlackjackRules(decks=6, max_hands=2),
}

MONTE_CARLO = ("1 deck, S17, no splitting", "6 decks, S17, DAS, split once")


def _setup_factory(rules: BlackjackRules):
    return _Setup(rules)


class _Setup:
    """Picklable (engine, policy) factory for worker processes."""

    def __init__(self, rules: BlackjackRules) -> None:
        self.rules = rules

    def __call__(self):
        solver = BlackjackSolver(self.rules)
        return Engine(Blackjack(self.rules)), engine_policy(solver_policy(solver))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hands", type=int, default=0, help="Monte Carlo hands per rule set")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    exact = {}
    for name, rules in EXACT.items():
        started = time.perf_counter()
        solver = BlackjackSolver(rules)
        exact[name] = solver.round_value()
        print(f"{name:<38} player expected value {exact[name] * 100:+.4f}%   "
              f"({time.perf_counter() - started:.1f} s)")
    for name in ("infinite deck, S17, DAS, split to 4", "6 decks, S17, DAS, split once"):
        print(f"\nBasic strategy chart, {name} (first decision; * = depends on the two cards)")
        print(format_chart(basic_strategy_chart(BlackjackSolver(EXACT[name]))))

    if args.hands:
        print()
        for name in MONTE_CARLO:
            started = time.perf_counter()
            chunk = -(-args.hands // args.workers)          # one chunk per worker: one solver each
            result = play_solo_parallel(_setup_factory(EXACT[name]), args.hands, seed=1,
                                        workers=args.workers, chunk=chunk)
            gap = (result.mean - exact[name]) / (result.margin / 1.96)
            print(f"Monte Carlo {name}: {result}  exact {exact[name]:+.5f}  "
                  f"gap {gap:+.2f} standard errors  ({time.perf_counter() - started:.0f} s)")


if __name__ == "__main__":
    main()
