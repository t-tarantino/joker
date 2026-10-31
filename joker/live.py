"""Live mode (DR-8): follow a real hand from what one observer actually sees.

At every step the session lists the observations that are still POSSIBLE (taken
from every possible world). One possible observation → it is applied
automatically (e.g. "the opponent drew a card": only its back is seen). Several →
the person chooses which one happened (e.g. "which card did you draw?"). The
person can therefore never enter something impossible, and no game-specific input
code is needed.

Two frontiers are kept:
- the PHYSICAL frontier (no regulatory rule trusted) lists what may happen, so a
  real player breaking a rule can still be recorded;
- the TRUSTED frontier (trust policy, A3) gives the belief. If it becomes empty, a
  violation was exposed: the belief is recomputed and the violation reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Any, Mapping

from .core.engine import Engine
from .core.events import Move, StepKind
from .core.observation import InformationState, MoveSeen, Observation
from .core.spec import Observer, Option, TrustPolicy
from .core.state import State, View
from .probability.belief import Unsupported, _check_supported, _expand, possible_worlds
from .probability.exchangeable import ExchangeableBelief, visible_class
from .probability.views import WorldsBelief

PHYSICAL = TrustPolicy(later=False, never=False)   # no regulatory rule trusted


@dataclass(frozen=True)
class Choice:
    observation: Observation

    @property
    def moves(self) -> tuple[MoveSeen, ...]:
        return tuple(p for p in self.observation.perceived if isinstance(p, MoveSeen))

    @property
    def own(self) -> Option | None:
        return self.observation.own


@dataclass(frozen=True)
class Pending:
    kind: StepKind
    actors: tuple
    choices: tuple[Choice, ...]

    @property
    def automatic(self) -> bool:
        return len(self.choices) == 1


@dataclass
class _Snapshot:
    physical: dict
    trusted: dict
    info: InformationState
    trust_used: TrustPolicy
    warnings: tuple
    by_user: bool
    label: str | None
    hand_start: tuple            # (worlds at hand start or None, hand number)


class LiveSession:
    def __init__(self, engine: Engine, observer: Observer,
                 match_state: Mapping[str, Any] | None = None,
                 trust: TrustPolicy = TrustPolicy()) -> None:
        self.engine = engine
        self.observer = observer
        self.trust = trust
        start = engine.new_hand(match_state)
        match = engine.match_state_of(start)
        self.info = InformationState(engine.game.name, engine.n, observer,
                                     tuple(sorted(match.items())), ())
        _check_supported(engine, self.info)
        self._physical: dict[State, Fraction] = {start: Fraction(1)}
        self._trusted: dict[State, Fraction] = {start: Fraction(1)}
        self.trust_used = trust
        self.warnings: tuple = ()
        self.hand = 1                                     # hands followed in this session
        self._start: dict | None = None                   # worlds at hand start, if carried over
        self._history: list[_Snapshot] = []
        self._pending: Pending | None = None
        self._pending_valid = False

    # --- reading ---------------------------------------------------------------------

    def worlds(self) -> list[tuple[View, Fraction]]:
        """Possible worlds under the trust policy, normalized. Never expose a single
        world to a person: only aggregates (non-leakage, S5.4)."""
        total = sum(self._trusted.values())
        return [(View(self.engine, s), w / total) for s, w in self._trusted.items()]

    def belief(self) -> WorldsBelief:
        return WorldsBelief(self.engine, self.worlds())

    @property
    def labels(self) -> list[str]:
        """Labels of the choices the person made, oldest first."""
        return [snap.label for snap in self._history if snap.by_user and snap.label]

    def pending(self) -> Pending | None:
        """What can happen next, or None when the hand is over in every world."""
        if not self._pending_valid:
            self._pending = self._compute_pending()
            self._pending_valid = True
        return self._pending

    # --- acting ----------------------------------------------------------------------

    def choose(self, index: int, label: str | None = None) -> None:
        pending = self.pending()
        if pending is None:
            raise ValueError("the hand is over")
        self._advance(pending.choices[index].observation, by_user=True, label=label)
        self.auto_advance()

    def auto_advance(self) -> None:
        while (pending := self.pending()) is not None and pending.automatic:
            self._advance(pending.choices[0].observation, by_user=False, label=None)

    def next_hand(self, reshuffle: bool = False) -> None:
        """Start the next hand of the match once this one is over. Cards in
        match-level zones stay out (Engine.next_hand, e.g. a blackjack discard
        tray), applied to EVERY possible world with its weight: exact also for cards
        that left unseen. reshuffle=True: all cards back in the deck (a new shoe).
        For a game without match-level zones it equals a new session. Undo can go
        back to the end of the previous hand."""
        if self.pending() is not None:
            raise ValueError("the hand is not over")
        engine = self.engine
        self._history.append(self._snapshot(by_user=True, label=None))

        def carry(frontier: dict) -> dict:                # normalized: keeps fractions small
            out: dict[State, Fraction] = {}
            total = sum(frontier.values())
            for s, w in frontier.items():
                child = engine.canonical(engine.next_hand(s, reshuffle))
                out[child] = out.get(child, Fraction(0)) + w / total
            return out

        self._physical, self._trusted = carry(self._physical), carry(self._trusted)
        matches = {tuple(sorted(engine.match_state_of(s).items())) for s in self._physical}
        if len(matches) != 1:
            raise Unsupported("the match state depends on cards the observer has not seen")
        self.info = InformationState(engine.game.name, engine.n, self.observer, matches.pop(), ())
        self._start = dict(self._trusted)
        self.hand += 1
        self._pending_valid = False

    def undo(self) -> bool:
        """Go back to just before the last choice the person made (or to the end of
        the previous hand, after next_hand)."""
        while self._history:
            snap = self._history.pop()
            self._physical, self._trusted = snap.physical, snap.trusted
            self.info, self.trust_used, self.warnings = snap.info, snap.trust_used, snap.warnings
            self._start, self.hand = snap.hand_start
            self._pending_valid = False
            if snap.by_user:
                return True
        return False

    # --- internals ---------------------------------------------------------------------

    def _snapshot(self, by_user: bool, label: str | None) -> _Snapshot:
        return _Snapshot(self._physical, self._trusted, self.info, self.trust_used,
                         self.warnings, by_user, label, (self._start, self.hand))

    def _advance(self, obs: Observation, by_user: bool, label: str | None) -> None:
        self._history.append(self._snapshot(by_user, label))
        info = self.info.extended(obs)
        physical = _step(self.engine, self._physical, obs, info, PHYSICAL)
        trusted = _step(self.engine, self._trusted, obs, info, self.trust_used)
        if not trusted:                                   # a violation was exposed (A3)
            worlds, self.trust_used, self.warnings = possible_worlds(self.engine, info, self.trust,
                                                                     self._start)
            trusted = dict(worlds)
        self._physical, self._trusted, self.info = physical, trusted, info
        self._pending_valid = False

    def _compute_pending(self) -> Pending | None:
        seen: dict[Observation, None] = {}
        for s in self._physical:
            for obs in self._candidates(s):
                seen.setdefault(obs, None)
        if not seen:
            return None
        first = next(iter(seen))
        return Pending(first.kind, first.actors, tuple(Choice(o) for o in seen))

    def _candidates(self, s: State) -> list[Observation]:
        engine, observer = self.engine, self.observer
        step = engine.next_step(s)
        if step.kind is StepKind.END:
            return []
        if step.kind is StepKind.AUTO:
            _, event = engine.apply(s)
            return [engine.observe(event, observer)]
        if step.kind is StepKind.NATURE:
            if s.pending:
                task = s.pending[0]
                src, dst = engine.zones[task.src], engine.zones[task.dst]
                if not src.ordered and not dst.ordered:   # fast path: only the card varies
                    visible = (src.visible_facets(observer, engine.all_facets)
                               | dst.visible_facets(observer, engine.all_facets))
                    attrs = {engine.cards[cid].type.restrict(visible) for cid in s.zones[task.src]}
                    return [Observation(s.step, step.kind, step.actors, None,
                                        (MoveSeen(task.src, task.dst, None, None, a),))
                            for a in attrs]
            out = []
            for outcome, _ in step.outcomes:
                _, event = engine.apply(s, outcome)
                out.append(engine.observe(event, observer))
            return out
        out = []
        options = [engine.legal_options(s, p, PHYSICAL) for p in step.actors]
        for combo in product(*options):
            _, event = engine.apply(s, dict(zip(step.actors, combo)))
            out.append(engine.observe(event, observer))
        return out


class ExchangeableSession:
    """Live mode for games that declare exchangeable unseen cards (Game.exchangeable).

    Instead of a frontier of worlds it keeps ONE representative world plus the set
    of cards the observer has fully seen ("pinned"). Any swap of two unpinned cards
    of the same visible class gives another possible world, all equally likely, so
    the belief is exact and combinatorial (ExchangeableBelief). Candidate
    observations are found by swapping each unseen card into the relevant zone.
    Same public API as LiveSession.
    """

    warnings: tuple = ()

    def __init__(self, engine: Engine, observer: Observer,
                 match_state: Mapping[str, Any] | None = None) -> None:
        if not engine.game.exchangeable:
            raise Unsupported(f"{engine.game.name} does not declare exchangeable unseen cards")
        if engine.regulatory_rules:
            raise Unsupported("regulatory rules may constrain unseen cards")
        self.engine = engine
        self.observer = observer
        self.trust_used = PHYSICAL
        self.world = engine.new_hand(match_state)
        match = engine.match_state_of(self.world)
        self.info = InformationState(engine.game.name, engine.n, observer,
                                     tuple(sorted(match.items())), ())
        _check_supported(engine, self.info)
        self.pinned: frozenset[int] = frozenset()
        self._history: list[tuple] = []          # (world, pinned, info, by_user, label)
        self._candidates: dict[Observation, tuple[State, Any]] = {}
        self._pending: Pending | None = None
        self._pending_valid = False

    # --- reading ---------------------------------------------------------------------

    def belief(self) -> ExchangeableBelief:
        return ExchangeableBelief(self.engine, self.world, self.pinned, self.observer)

    @property
    def labels(self) -> list[str]:
        return [label for *_, by_user, label in self._history if by_user and label]

    def pending(self) -> Pending | None:
        if not self._pending_valid:
            self._candidates = self._compute_candidates()
            if self._candidates:
                first = next(iter(self._candidates))
                self._pending = Pending(first.kind, first.actors,
                                        tuple(Choice(o) for o in self._candidates))
            else:
                self._pending = None
            self._pending_valid = True
        return self._pending

    # --- acting ----------------------------------------------------------------------

    def choose(self, index: int, label: str | None = None) -> None:
        pending = self.pending()
        if pending is None:
            raise ValueError("the hand is over")
        self._advance(pending.choices[index].observation, by_user=True, label=label)
        self.auto_advance()

    def auto_advance(self) -> None:
        while (pending := self.pending()) is not None and pending.automatic:
            self._advance(pending.choices[0].observation, by_user=False, label=None)

    def undo(self) -> bool:
        while self._history:
            self.world, self.pinned, self.info, by_user, _ = self._history.pop()
            self._pending_valid = False
            if by_user:
                return True
        return False

    # --- internals ---------------------------------------------------------------------

    def _advance(self, obs: Observation, by_user: bool, label: str | None) -> None:
        self.pending()
        variant, outcome = self._candidates[obs]
        child, event = self.engine.apply(variant, outcome)
        if self.engine.observe(event, self.observer) != obs:
            raise AssertionError("candidate observation is not reproducible")
        pinned = self._pin(variant, event)
        self._history.append((self.world, self.pinned, self.info, by_user, label))
        self.world, self.pinned, self.info = child, pinned, self.info.extended(obs)
        self._pending_valid = False

    def _compute_candidates(self) -> dict[Observation, tuple[State, Any]]:
        engine, s = self.engine, self.world
        step = engine.next_step(s)
        out: dict[Observation, tuple[State, Any]] = {}

        def add(variant: State, outcome: Any) -> None:
            _, event = engine.apply(variant, outcome)
            out.setdefault(engine.observe(event, self.observer), (variant, outcome))

        if step.kind is StepKind.END:
            return out
        if step.kind is StepKind.AUTO:
            add(s, None)
        elif step.kind is StepKind.NATURE and s.pending:
            for variant, cid in self._placements(s.pending[0].src):
                add(variant, cid)
        elif step.kind is StepKind.NATURE:
            for outcome, _ in step.outcomes:
                add(s, outcome)
        else:
            if len(step.actors) != 1:
                raise Unsupported("simultaneous choices are not supported by the exchangeable method")
            p = step.actors[0]
            variants = [s]
            for zone in (z for z in engine.zones.values() if z.owner == p):
                variants.extend(v for v, _ in self._placements(zone.name, swaps_only=True))
            for variant in variants:
                for opt in engine.legal_options(variant, p, PHYSICAL):
                    add(variant, {p: opt})
        return out

    def _placements(self, zone: str, swaps_only: bool = False):
        """(variant, card id) pairs: each card that may be in `zone`, placed there."""
        s, engine = self.world, self.engine
        if not swaps_only:
            for cid in s.zones[zone]:
                yield s, cid
        unpinned_here = [c for c in s.zones[zone] if c not in self.pinned]
        seen_types = {engine.cards[c].type for c in s.zones[zone]}
        for other, ids in s.zones.items():
            if other == zone:
                continue
            for cid in ids:
                t = engine.cards[cid].type
                if cid in self.pinned or t in seen_types:
                    continue
                cls = visible_class(engine, t)
                partner = next((c for c in unpinned_here
                                if visible_class(engine, engine.cards[c].type) == cls), None)
                if partner is None:
                    continue
                seen_types.add(t)
                yield self._swap(s, cid, partner), cid

    def _swap(self, s: State, a: int, b: int) -> State:
        zones = dict(s.zones)
        za = next(z for z, ids in zones.items() if a in ids)
        zb = next(z for z, ids in zones.items() if b in ids)
        for zone, old, new in ((za, a, b), (zb, b, a)):
            ids = tuple(new if c == old else c for c in zones[zone])
            zones[zone] = ids if self.engine.zones[zone].ordered else tuple(sorted(ids))
        return State(zones, dict(s.vars), s.phase, s.pending, s.step)

    def _pin(self, variant: State, event) -> frozenset[int]:
        """Cards fully seen during the event become pinned. A card moving unseen
        among cards the observer could tell apart breaks exchangeability."""
        engine = self.engine
        pinned = set(self.pinned)
        zones = {z: list(ids) for z, ids in variant.zones.items()}
        for prim in event.primitives:
            if not isinstance(prim, Move):
                continue
            visible = (engine.zones[prim.src].visible_facets(self.observer, engine.all_facets)
                       | engine.zones[prim.dst].visible_facets(self.observer, engine.all_facets))
            card_type = engine.cards[prim.card].type
            if card_type.restrict(visible) == card_type.facets:
                pinned.add(prim.card)
            else:
                looks = card_type.restrict(visible)
                alike = [c for c in zones[prim.src]
                         if c != prim.card and engine.cards[c].type.restrict(visible) == looks]
                if alike and (prim.card in pinned or any(c in pinned for c in alike)):
                    raise Unsupported("a seen card moved unseen among look-alike cards")
            zones[prim.src].remove(prim.card)
            zones[prim.dst].append(prim.card)
        return frozenset(pinned)


def _step(engine: Engine, frontier: dict[State, Fraction], obs: Observation,
          info: InformationState, trust: TrustPolicy) -> dict[State, Fraction]:
    out: dict[State, Fraction] = {}
    for s, w in frontier.items():
        for child, cw in _expand(engine, s, obs, info, trust):
            child = engine.canonical(child)              # merge copies of a card (S1.1)
            out[child] = out.get(child, Fraction(0)) + w * cw
    return out
