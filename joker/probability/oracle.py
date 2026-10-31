"""Brute-force oracle (probability.md §6.1) — tests only, tiny games only.

Enumerates EVERY full history of the right length from the start of the hand,
with no pruning and no merging, and keeps those whose observation sequence equals
the observer's. The exact method must always agree with it.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import product

from ..core.engine import Engine
from ..core.events import StepKind
from ..core.observation import InformationState
from ..core.spec import TrustPolicy
from ..core.state import State


def oracle_worlds(engine: Engine, info: InformationState,
                  trust: TrustPolicy = TrustPolicy(),
                  start: dict[State, Fraction] | None = None) -> dict[State, Fraction]:
    """`start`: worlds at the start of the hand (cards carried over from earlier
    hands); default: a fresh new_hand."""
    target = info.observations
    observer = info.observer
    result: dict[State, Fraction] = {}

    def dfs(s: State, weight: Fraction, seen: tuple) -> None:
        k = len(seen)
        if k == len(target):
            if seen == target:
                result[s] = result.get(s, Fraction(0)) + weight
            return
        step = engine.next_step(s)
        if step.kind is StepKind.END:
            return
        if step.kind is StepKind.AUTO:
            child, event = engine.apply(s)
            dfs(child, weight, seen + (engine.observe(event, observer),))
        elif step.kind is StepKind.NATURE:
            for outcome, p in step.outcomes:
                child, event = engine.apply(s, outcome)
                dfs(child, weight * p, seen + (engine.observe(event, observer),))
        else:
            joints = [dict(zip(step.actors, combo)) for combo in
                      product(*(engine.legal_options(s, p, trust) for p in step.actors))]
            branches = []
            for joint in joints:
                child, event = engine.apply(s, joint)
                branches.append((child, engine.observe(event, observer)))
            for child, obs in branches:
                same = sum(1 for _, other in branches if other == obs)   # |C| for this branch
                dfs(child, weight / same, seen + (obs,))

    for s, w in (start or {engine.new_hand(dict(info.match_state)): Fraction(1)}).items():
        dfs(s, w, ())
    return result
