"""The engine: the referee that holds the physical state and applies steps
(core-contracts.md §3.7, §5).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Mapping

from .card import Card, build_cards
from .events import DrawTask, Event, Move, SetVar, Step, StepKind
from .spec import (END_HAND, NATURE, AutoPhase, CardRef, ChoicePhase, Game, NaturePhase,
                   Observer, Option, PerPlayer, Rule, RuleClass, TrustPolicy, Var,
                   VarInstance, Zone)
from .state import State, View

TOP = "top"
BOTTOM = "bottom"


class GameError(Exception):
    """The game definition did something the contracts forbid."""


class IllegalInput(Exception):
    """An outcome that is not physically possible in the current state."""


class Ctx:
    """The only door to the primitives M1 / M2 and to queued Nature draws (S7.2)."""

    def __init__(self, engine: Engine, state: State) -> None:
        self._engine = engine
        self._zones = dict(state.zones)
        self._vars = dict(state.vars)
        self._phase = state.phase
        self._step = state.step
        self.remaining: list[DrawTask] = list(state.pending)
        self.new_tasks: list[DrawTask] = []
        self.primitives: list[Move | SetVar] = []

    @property
    def state(self) -> View:
        """Live view, reflecting every primitive applied so far in this step."""
        return View(self._engine, State(self._zones, self._vars, self._phase, (), self._step))

    def move(self, card: Card | CardRef | int, to: str, position: Any = None) -> int:
        """M1. `card` may be a Card, a card id, or a CardRef (resolved to the lowest
        matching copy — any fixed rule is fine by copy symmetry, S1.1). Returns the
        id of the card moved."""
        engine = self._engine
        cid = self._resolve(card)
        src = next((z for z, ids in self._zones.items() if cid in ids), None)
        if src is None:
            raise GameError(f"card {cid} is in no zone")
        if to not in engine.zones:
            raise GameError(f"unknown zone {to!r}")
        src_ids = self._zones[src]
        idx = src_ids.index(cid)
        self._zones[src] = src_ids[:idx] + src_ids[idx + 1:]
        dst_ids = self._zones[to]
        if engine.zones[to].ordered:
            if position in (None, TOP):
                pos = len(dst_ids)
            elif position == BOTTOM:
                pos = 0
            else:
                pos = int(position)
            self._zones[to] = dst_ids[:pos] + (cid,) + dst_ids[pos:]
            dst_pos: int | None = pos
        else:
            self._zones[to] = tuple(sorted(dst_ids + (cid,)))
            dst_pos = None
        src_pos = idx if engine.zones[src].ordered else None
        self.primitives.append(Move(cid, src, to, src_pos, dst_pos))
        return cid

    def set(self, name: str, value: Any) -> None:
        """M2."""
        if name not in self._engine.vars:
            raise GameError(f"unknown variable {name!r}")
        self._vars[name] = value
        self.primitives.append(SetVar(name, value))

    def draw_random(self, src: str, dst: str, n: int = 1) -> None:
        """Queue n Nature steps, each drawing a uniformly random card of `src` (DR-2)."""
        for name in (src, dst):
            if name not in self._engine.zones:
                raise GameError(f"unknown zone {name!r}")
        self.new_tasks.extend(DrawTask(src, dst) for _ in range(n))

    def _resolve(self, card: Card | CardRef | int) -> int:
        if isinstance(card, int):
            return card
        if isinstance(card, Card):
            return card.id
        if isinstance(card, CardRef):
            zone = self._engine.zones[card.zone]
            visible = zone.visible_facets(card.seen_by, self._engine.all_facets)
            for cid in self._zones[card.zone]:
                if self._engine.cards[cid].type.restrict(visible) == card.attrs:
                    return cid
            raise IllegalInput(f"no card matching {card} in {card.zone!r}")
        raise TypeError(f"cannot move {card!r}")


@dataclass
class Trace:
    """A complete record of a simulated or replayed hand."""

    match_state: dict
    outcomes: list = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    states: list[State] = field(default_factory=list)   # states[0] = start, states[k+1] after events[k]

    @property
    def final(self) -> State:
        return self.states[-1]


Policy = Callable[[View, int, tuple[Option, ...], random.Random], Option]


def random_policy(view: View, player: int, options: tuple[Option, ...], rng: random.Random) -> Option:
    return rng.choice(options)


class Engine:
    def __init__(self, game: Game, n_players: int | None = None) -> None:
        self.game = game
        self.n = n_players if n_players is not None else game.players
        self.cards: tuple[Card, ...] = build_cards(game.deck)
        self.all_facets = frozenset(f for c in self.cards for f in c.type.facet_names)
        type_index: dict = {}
        self._type_of = [type_index.setdefault(c.type, len(type_index)) for c in self.cards]
        self._ids_of_type: list[list[int]] = [[] for _ in type_index]
        for card in self.cards:
            self._ids_of_type[self._type_of[card.id]].append(card.id)
        self.zones: dict[str, Zone] = {}
        for item in game.zones:
            for zone in self._expand(item):
                if zone.name in self.zones:
                    raise GameError(f"duplicate zone {zone.name!r}")
                self.zones[zone.name] = zone
        self.vars: dict[str, VarInstance] = {}
        for match_level, declared in ((True, game.match_vars), (False, game.hand_vars)):
            for var in declared:
                for inst in self._expand_var(var, match_level):
                    self.vars[inst.name] = inst
        self._validate()

    # --- setup ---------------------------------------------------------------------

    def _expand(self, item: Zone | PerPlayer) -> list[Zone]:
        if isinstance(item, PerPlayer):
            return [item.make(p) for p in range(self.n)]
        return [item]

    def _expand_var(self, var: Var, match_level: bool) -> list[VarInstance]:
        if var.per_player:
            return [VarInstance(f"{var.name}[{p}]", var.initial, var.visible, match_level, p)
                    for p in range(self.n)]
        return [VarInstance(var.name, var.initial, var.visible, match_level, None)]

    def _validate(self) -> None:
        g = self.game
        if g.deck_zone not in self.zones:
            raise GameError(f"deck zone {g.deck_zone!r} is not declared")
        if g.initial_phase not in g.phases:
            raise GameError(f"initial phase {g.initial_phase!r} is not declared")
        for zone in self.zones.values():
            if zone.refill_from is not None and zone.refill_from not in self.zones:
                raise GameError(f"zone {zone.name!r} refills from unknown zone")

    def zone(self, name: str) -> Zone:
        return self.zones[name]

    def view(self, s: State) -> View:
        return View(self, s)

    def canonical(self, s: State) -> State:
        """The representative of all states that differ only by which copy of a card
        type sits where (copies are interchangeable, S1.1; copy labels are never
        observable, S1.1b): copies are handed out in a fixed order of zones.
        Requirement: game variables never hold card ids (true for every game so far).
        With no duplicate cards it returns the state unchanged."""
        pools = [iter(ids) for ids in self._ids_of_type]
        zones = {}
        for name in sorted(s.zones):
            ids = tuple(next(pools[self._type_of[i]]) for i in s.zones[name])
            zones[name] = ids if self.zones[name].ordered else tuple(sorted(ids))
        return State({n: zones[n] for n in s.zones}, s.vars, s.phase, s.pending, s.step)

    @property
    def regulatory_rules(self) -> list[Rule]:
        return [r for ph in self.game.phases.values() if isinstance(ph, ChoicePhase) for r in ph.rules]

    # --- hand lifecycle -----------------------------------------------------------------

    def new_hand(self, match_state: Mapping[str, Any] | None = None) -> State:
        """All cards start in the deck zone; hand variables reset; match variables from
        `match_state` (S6.1: the match state is an input of the hand)."""
        zones = {name: () for name in self.zones}
        zones[self.game.deck_zone] = tuple(c.id for c in self.cards)
        variables = {name: v.initial for name, v in self.vars.items()}
        for name, value in (match_state or {}).items():
            if name not in self.vars or not self.vars[name].match_level:
                raise GameError(f"{name!r} is not a match variable")
            variables[name] = value
        return State(zones, variables, self.game.initial_phase, (), 0)

    def next_hand(self, s: State, reshuffle: bool = False) -> State:
        """The start of the next hand, from the end of this one (S6.1). Runs
        Game.end_hand; then cards in match-level zones stay where they are, every
        other card goes back to the deck zone, hand variables reset. reshuffle=True:
        every card goes back to the deck zone (a new shoe), match variables kept.
        A game without match-level zones gets exactly new_hand(match_state_after(s))."""
        if s.phase != END_HAND or s.pending:
            raise IllegalInput("the hand is not over")
        ctx = Ctx(self, s)
        self.game.end_hand(View(self, s), ctx)
        if ctx.new_tasks:
            raise GameError("end_hand cannot draw cards")
        match = {name: ctx._vars[name] for name, v in self.vars.items() if v.match_level}
        start = self.new_hand(match)
        if reshuffle:
            return start
        zones = {name: (ids if self.zones[name].match_level else ()) for name, ids in ctx._zones.items()}
        kept = {cid for ids in zones.values() for cid in ids}
        back = tuple(c.id for c in self.cards if c.id not in kept)
        deck = self.game.deck_zone
        zones[deck] = zones[deck] + back if self.zones[deck].ordered else tuple(sorted(zones[deck] + back))
        return State(zones, start.vars, start.phase, (), 0)

    def match_state_of(self, s: State) -> dict[str, Any]:
        return {name: s.vars[name] for name, v in self.vars.items() if v.match_level}

    def match_state_after(self, s: State) -> dict[str, Any]:
        """Run Game.end_hand and return the match state for the next hand."""
        ctx = Ctx(self, s)
        self.game.end_hand(View(self, s), ctx)
        return {name: ctx._vars[name] for name, v in self.vars.items() if v.match_level}

    # --- steps ------------------------------------------------------------------------

    def next_step(self, s: State) -> Step:
        if s.pending:
            task = s.pending[0]
            ids = s.zones[task.src]
            if not ids:
                raise GameError(f"draw from empty zone {task.src!r}")
            p = Fraction(1, len(ids))
            return Step(StepKind.NATURE, (NATURE,), outcomes=tuple((cid, p) for cid in ids))
        if s.phase == END_HAND:
            return Step(StepKind.END, ())
        phase = self.game.phases[s.phase]
        view = View(self, s)
        if isinstance(phase, AutoPhase):
            return Step(StepKind.AUTO, ())
        if isinstance(phase, NaturePhase):
            outcomes = tuple((o, Fraction(p)) for o, p in phase.distribution(view))
            if sum(p for _, p in outcomes) != 1:
                raise GameError(f"distribution of {s.phase!r} does not sum to 1")
            return Step(StepKind.NATURE, (NATURE,), outcomes=outcomes)
        if isinstance(phase, ChoicePhase):
            actors = tuple(phase.actors(view))
            options = {p: tuple(phase.options(view, p)) for p in actors}
            return Step(StepKind.CHOICE, actors, options=options)
        raise GameError(f"phase {s.phase!r} has an unknown type")

    def legal_options(self, s: State, player: int, trust: TrustPolicy | None = None) -> tuple[Option, ...]:
        """Physically possible options filtered by regulatory rules. trust=None enforces
        every rule (live play); a TrustPolicy enforces only the trusted ones (belief)."""
        phase = self.game.phases[s.phase]
        view = View(self, s)
        rules = [r for r in phase.rules if trust is None or trust.trusts(r, player)]
        return tuple(o for o in phase.options(view, player)
                     if all(r.allowed(view, player, o) for r in rules))

    def violations(self, s: State, joint: Mapping[int, Option]) -> list[tuple[int, str, RuleClass]]:
        """Regulatory rules broken by a joint choice (input validation, A3)."""
        phase = self.game.phases[s.phase]
        view = View(self, s)
        return [(p, r.name, r.klass) for p, o in joint.items() for r in phase.rules
                if not r.allowed(view, p, o)]

    def apply(self, s: State, outcome: Any = None) -> tuple[State, Event]:
        step = self.next_step(s)
        ctx = Ctx(self, s)
        view = View(self, s)
        if step.kind is StepKind.END:
            raise IllegalInput("the hand is over")
        if step.kind is StepKind.NATURE and s.pending:
            if outcome not in s.zones[s.pending[0].src]:
                raise IllegalInput(f"card {outcome!r} is not in {s.pending[0].src!r}")
            task = ctx.remaining.pop(0)
            ctx.move(outcome, task.dst)
            next_phase = s.phase
        elif step.kind is StepKind.NATURE:
            if outcome not in {o for o, _ in step.outcomes}:
                raise IllegalInput(f"impossible chance outcome {outcome!r}")
            next_phase = self.game.phases[s.phase].apply(view, outcome, ctx)
        elif step.kind is StepKind.AUTO:
            next_phase = self.game.phases[s.phase].run(view, ctx)
        else:
            if not isinstance(outcome, Mapping) or set(outcome) != set(step.actors):
                raise IllegalInput(f"expected one option for each of {step.actors}")
            for p, o in outcome.items():
                if o not in step.options[p]:
                    raise IllegalInput(f"option {o!r} is not physically possible for player {p}")
            next_phase = self.game.phases[s.phase].apply(view, dict(outcome), ctx)
        if next_phase != END_HAND and next_phase not in self.game.phases:
            raise GameError(f"phase {s.phase!r} returned unknown phase {next_phase!r}")
        pending = ctx.remaining + ctx.new_tasks
        for name, zone in self.zones.items():
            if zone.refill_from is not None and not ctx._zones[name] and ctx._zones[zone.refill_from]:
                task = DrawTask(zone.refill_from, name)
                if task not in pending:
                    pending.insert(0, task)
        new_state = State(ctx._zones, ctx._vars, next_phase, tuple(pending), s.step + 1)
        event = Event(s.step, step.kind, step.actors,
                      dict(outcome) if step.kind is StepKind.CHOICE else outcome,
                      tuple(ctx.primitives))
        return new_state, event

    # --- simulation and replay -----------------------------------------------------------

    def sample_nature(self, s: State, rng: random.Random) -> Any:
        outcomes = self.next_step(s).outcomes
        r, acc = Fraction(rng.random()), Fraction(0)
        for outcome, p in outcomes:
            acc += p
            if r < acc:
                return outcome
        return outcomes[-1][0]

    def play(self, rng: random.Random, policy: Policy = random_policy,
             match_state: Mapping[str, Any] | None = None, max_steps: int = 100_000,
             enforce_rules: bool = True, start: State | None = None) -> Trace:
        """Simulate one hand. With enforce_rules=False the policy chooses among all
        physically possible options (used to simulate players who break rules).
        `start`: the start of the hand when cards carried over (Engine.next_hand)."""
        s = self.new_hand(match_state) if start is None else start
        match_state = self.match_state_of(s) if start is not None else match_state
        trace = Trace(dict(match_state or {}), states=[s])
        for _ in range(max_steps):
            step = self.next_step(s)
            if step.kind is StepKind.END:
                return trace
            if step.kind is StepKind.AUTO:
                outcome = None
            elif step.kind is StepKind.NATURE:
                outcome = self.sample_nature(s, rng)
            else:
                outcome = {}
                for p in step.actors:
                    opts = self.legal_options(s, p) if enforce_rules else step.options[p]
                    outcome[p] = policy(View(self, s), p, opts, rng)
            s, event = self.apply(s, outcome)
            trace.outcomes.append(outcome)
            trace.events.append(event)
            trace.states.append(s)
        raise GameError("hand did not end within max_steps")

    def replay(self, match_state: Mapping[str, Any] | None, outcomes: list) -> Trace:
        s = self.new_hand(match_state)
        trace = Trace(dict(match_state or {}), states=[s])
        for outcome in outcomes:
            s, event = self.apply(s, outcome)
            trace.outcomes.append(outcome)
            trace.events.append(event)
            trace.states.append(s)
        return trace

    def check_invariants(self, s: State) -> None:
        """Card conservation: every card in exactly one zone; unordered zones sorted."""
        seen: list[int] = []
        for name, ids in s.zones.items():
            if not self.zones[name].ordered and list(ids) != sorted(ids):
                raise AssertionError(f"unordered zone {name!r} not canonical")
            seen.extend(ids)
        if sorted(seen) != [c.id for c in self.cards]:
            raise AssertionError("card conservation violated")

    # --- observation (delegates to observation.py) -----------------------------------------

    def observe(self, event: Event, observer: Observer):
        from .observation import observe
        return observe(self, event, observer)

    def info_state(self, trace: Trace, observer: Observer, upto: int | None = None):
        """Information state of `observer` after the first `upto` events (default: all)."""
        from .observation import info_state
        return info_state(self, trace, observer, upto)
