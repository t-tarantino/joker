"""Observations are derived, never declared (S5.2). Information state = the
observation history of one observer (S5.1). core-contracts.md §6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .card import FrozenFacets
from .events import Event, Move, SetVar, StepKind
from .spec import Observer, selector_matches

if TYPE_CHECKING:
    from .engine import Engine, Trace


@dataclass(frozen=True)
class MoveSeen:
    """A card move as perceived: zones, positions (ordered zones only) and the
    attributes of the facets visible in the source or destination zone. Never a CardId."""

    src: str
    dst: str
    src_pos: int | None
    dst_pos: int | None
    attrs: FrozenFacets


@dataclass(frozen=True)
class VarSeen:
    name: str
    value: Any


@dataclass(frozen=True)
class Observation:
    step: int
    kind: StepKind               # control flow is public (S5.5)
    actors: tuple
    own: Any                     # the observer's own option, if it was an actor (S5.6)
    perceived: tuple


@dataclass(frozen=True)
class InformationState:
    game: str
    n_players: int
    observer: Observer
    match_state: tuple           # ((name, value), ...) visible to the observer at hand start
    observations: tuple          # perfect recall: the full history (S5.1)

    def extended(self, observation: Observation) -> InformationState:
        """Add one observation (e.g. live mode input)."""
        return InformationState(self.game, self.n_players, self.observer, self.match_state,
                                self.observations + (observation,))


def observe(engine: Engine, event: Event, observer: Observer) -> Observation:
    perceived: list[MoveSeen | VarSeen] = []
    for prim in event.primitives:
        if isinstance(prim, Move):
            src, dst = engine.zones[prim.src], engine.zones[prim.dst]
            if src.count_seen(observer) or dst.count_seen(observer):
                visible = (src.visible_facets(observer, engine.all_facets)
                           | dst.visible_facets(observer, engine.all_facets))
                attrs = engine.cards[prim.card].type.restrict(visible)
                perceived.append(MoveSeen(prim.src, prim.dst, prim.src_pos, prim.dst_pos, attrs))
        elif isinstance(prim, SetVar):
            var = engine.vars[prim.name]
            if selector_matches(var.visible, observer, var.owner):
                perceived.append(VarSeen(prim.name, prim.value))
    own = None
    if event.kind is StepKind.CHOICE and isinstance(observer, int) and observer in event.actors:
        own = event.outcome[observer]
    return Observation(event.step, event.kind, event.actors, own, tuple(perceived))


def info_state(engine: Engine, trace: Trace, observer: Observer, upto: int | None = None) -> InformationState:
    visible_match = tuple(
        (name, value) for name, value in sorted(engine.match_state_of(trace.states[0]).items())
        if selector_matches(engine.vars[name].visible, observer, engine.vars[name].owner)
    )
    events = trace.events if upto is None else trace.events[:upto]
    return InformationState(engine.game.name, engine.n, observer, visible_match,
                            tuple(observe(engine, e, observer) for e in events))
