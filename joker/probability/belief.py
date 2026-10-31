"""Belief over hidden cards — exact incremental enumeration (probability.md §2–§3,
§6.2, §7). Works ONLY from an InformationState, never from a physical state (S5.4).

A world is a full history; it is possible iff replaying it reproduces the
observer's observations under the trusted rules (S7.4). Worlds that reach the same
state are merged (valid because the whole control state lives in State, DR-1),
and so are worlds that differ only by which copy of a card is where (S1.1,
Engine.canonical) — without this, every seen card of a multi-copy deck would
multiply the worlds by its number of copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Any

from ..core.engine import Engine
from ..core.events import StepKind
from ..core.observation import InformationState, MoveSeen, Observation
from ..core.spec import RuleClass, TrustPolicy
from ..core.state import State, View
from .queries import Query

ASSUMPTIONS = ("A1", "A1.1", "A3", "S2.2:uniform", "S7.4")
CHOICE_MODEL = "UniformNoInformation"


class Unsupported(Exception):
    """The question is outside what Goal 1 supports (e.g. hidden zone counts, S1.5)."""


class InconsistentObservations(Exception):
    """No world matches the observations, even distrusting every regulatory rule."""


@dataclass(frozen=True)
class ViolationDetected:
    """Trusting `rule` for `player` left no possible world: a violation was exposed (A3)."""

    player: int
    rule: str


@dataclass(frozen=True)
class BeliefResult:
    value: Any
    exact: bool
    support: int                     # number of distinct possible worlds (merged states)
    trust_policy: TrustPolicy
    choice_model: str
    assumptions: tuple
    warnings: tuple


class _NoWorld(Exception):
    def __init__(self, step: int) -> None:
        super().__init__(step)
        self.step = step


def belief(engine: Engine, info: InformationState, query: Query,
           trust: TrustPolicy = TrustPolicy()) -> BeliefResult:
    worlds, policy, warnings = possible_worlds(engine, info, trust)
    total = sum(w for _, w in worlds)
    normalized = [(View(engine, s), w / total) for s, w in worlds]
    return BeliefResult(query.evaluate(engine, normalized), True, len(worlds), policy,
                        CHOICE_MODEL, ASSUMPTIONS, warnings)


def possible_worlds(engine: Engine, info: InformationState, trust: TrustPolicy = TrustPolicy(),
                    start: dict[State, Fraction] | None = None
                    ) -> tuple[list[tuple[State, Fraction]], TrustPolicy, tuple]:
    """Possible worlds with unnormalized weights, the trust policy finally used, and
    warnings (a detected violation triggers a recompute, never a crash — A3).
    `start`: the possible worlds at the start of the hand, when cards carried over
    from earlier hands (Engine.next_hand); default: a fresh new_hand."""
    _check_supported(engine, info)
    try:
        return _enumerate(engine, info, trust, start), trust, ()
    except _NoWorld:
        pass
    for player in range(engine.n):
        for rule in engine.regulatory_rules:
            if rule.klass is RuleClass.IMMEDIATE or not trust.trusts(rule, player):
                continue
            relaxed = trust.with_override(player, rule.name, False)
            try:
                worlds = _enumerate(engine, info, relaxed, start)
            except _NoWorld:
                continue
            return worlds, relaxed, (ViolationDetected(player, rule.name),)
    raise InconsistentObservations("no world reproduces the observations")


def _check_supported(engine: Engine, info: InformationState) -> None:
    hidden_counts = [z.name for z in engine.zones.values() if not z.count_seen(info.observer)]
    if hidden_counts:
        raise Unsupported(f"zone counts hidden from the observer: {hidden_counts} (S1.5)")
    match_vars = {name for name, v in engine.vars.items() if v.match_level}
    if {name for name, _ in info.match_state} != match_vars:
        raise Unsupported("part of the match state is hidden from the observer")


def _enumerate(engine: Engine, info: InformationState, trust: TrustPolicy,
               start: dict[State, Fraction] | None = None) -> list[tuple[State, Fraction]]:
    frontier = dict(start) if start else {engine.new_hand(dict(info.match_state)): Fraction(1)}
    for obs in info.observations:
        nxt: dict[State, Fraction] = {}
        for s, w in frontier.items():
            for child, cw in _expand(engine, s, obs, info, trust):
                child = engine.canonical(child)          # merge copies of a card (S1.1)
                nxt[child] = nxt.get(child, Fraction(0)) + w * cw
        if not nxt:
            raise _NoWorld(obs.step)
        frontier = nxt
    return list(frontier.items())


def _expand(engine: Engine, s: State, obs: Observation, info: InformationState,
            trust: TrustPolicy) -> list[tuple[State, Fraction]]:
    """Children of `s` that reproduce `obs`, with the step weight (probability.md §3)."""
    step = engine.next_step(s)
    if step.kind is not obs.kind or step.actors != obs.actors:   # control flow is public
        return []
    observer = info.observer
    if step.kind is StepKind.AUTO:
        child, event = engine.apply(s)
        return [(child, Fraction(1))] if engine.observe(event, observer) == obs else []
    if step.kind is StepKind.NATURE:
        out = []
        prefilter = _draw_prefilter(engine, s, obs, observer)
        for outcome, p in step.outcomes:
            if prefilter is not None and not prefilter(outcome):
                continue
            child, event = engine.apply(s, outcome)
            if engine.observe(event, observer) == obs:
                out.append((child, p))
        return out
    # CHOICE — Goal 1 "no information" mode: w = 1 / |C|, where C are the allowed joint
    # options that reproduce the observation (a choice never re-weights the past).
    per_actor = []
    for p in step.actors:
        opts = engine.legal_options(s, p, trust)
        if p == observer:
            opts = tuple(o for o in opts if o == obs.own)
        per_actor.append(opts)
    matches = []
    for combo in product(*per_actor):
        child, event = engine.apply(s, dict(zip(step.actors, combo)))
        if engine.observe(event, observer) == obs:
            matches.append(child)
    if not matches:
        return []
    w = Fraction(1, len(matches))
    return [(child, w) for child in matches]


def _draw_prefilter(engine: Engine, s: State, obs: Observation, observer):
    """Cheap test for queued draws: the drawn card's visible attributes must match the
    first perceived move. Only an optimization — every survivor is fully checked."""
    if not s.pending or not obs.perceived or not isinstance(obs.perceived[0], MoveSeen):
        return None
    task = s.pending[0]
    seen = obs.perceived[0]
    visible = (engine.zones[task.src].visible_facets(observer, engine.all_facets)
               | engine.zones[task.dst].visible_facets(observer, engine.all_facets))
    return lambda cid: engine.cards[cid].type.restrict(visible) == seen.attrs
