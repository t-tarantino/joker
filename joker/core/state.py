"""Physical state (the referee's truth) and the read-only View game code uses
(core-contracts.md §4). Knowledge is never stored here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .card import FACE, Card, Facet
from .spec import CardRef

if TYPE_CHECKING:
    from .engine import Engine


class State:
    """Immutable by convention. Unordered zones keep their card ids sorted, so states
    reached through different orders compare equal (used for merging worlds)."""

    __slots__ = ("zones", "vars", "phase", "pending", "step", "_hash")

    def __init__(self, zones: dict[str, tuple[int, ...]], vars: dict[str, Any],
                 phase: str, pending: tuple, step: int) -> None:
        self.zones = zones
        self.vars = vars
        self.phase = phase
        self.pending = pending      # queued automatic steps (DrawTask), part of the state
        self.step = step
        self._hash: int | None = None

    def key(self) -> tuple:
        return (
            tuple(sorted(self.zones.items())),
            tuple(sorted(self.vars.items(), key=lambda kv: kv[0])),
            self.phase,
            self.pending,
            self.step,
        )

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(self.key())
        return self._hash

    def __eq__(self, other: object) -> bool:
        return isinstance(other, State) and self.key() == other.key()

    def __repr__(self) -> str:
        return f"State(step={self.step}, phase={self.phase!r}, pending={len(self.pending)})"


class View:
    """Read-only access to a state for game code, rules, derived functions and queries."""

    def __init__(self, engine: Engine, state: State) -> None:
        self._engine = engine
        self._state = state

    @property
    def raw(self) -> State:
        return self._state

    @property
    def n_players(self) -> int:
        return self._engine.n

    def cards(self, zone: str) -> list[Card]:
        return [self._engine.cards[i] for i in self._state.zones[zone]]

    def count(self, zone: str) -> int:
        return len(self._state.zones[zone])

    def zone_of(self, card: Card | int) -> str:
        cid = card if isinstance(card, int) else card.id
        for name, ids in self._state.zones.items():
            if cid in ids:
                return name
        raise KeyError(cid)

    def card_refs(self, zone: str, seen_by: int) -> list[CardRef]:
        """The distinct cards of `zone` as player `seen_by` can tell them apart (S7.8)."""
        visible = self._engine.zones[zone].visible_facets(seen_by, self._engine.all_facets)
        refs: list[CardRef] = []
        seen: set = set()
        for card in self.cards(zone):
            attrs = card.type.restrict(visible)
            if attrs not in seen:
                seen.add(attrs)
                refs.append(CardRef(zone, seen_by, attrs))
        return refs

    def ref_of(self, card: Card, seen_by: int) -> CardRef:
        """The CardRef of a card in its current zone, as player `seen_by` sees it."""
        zone = self.zone_of(card)
        visible = self._engine.zones[zone].visible_facets(seen_by, self._engine.all_facets)
        return CardRef(zone, seen_by, card.type.restrict(visible))

    def holds(self, zone: str, facet: Facet = FACE, **attrs: Any) -> bool:
        return any(c.matches(facet, **attrs) for c in self.cards(zone))

    def count_matching(self, zone: str, facet: Facet = FACE, **attrs: Any) -> int:
        return sum(1 for c in self.cards(zone) if c.matches(facet, **attrs))

    def holder_of(self, facet: Facet = FACE, **attrs: Any) -> str | None:
        """Zone holding the first card that matches (None if no card matches)."""
        for name, ids in self._state.zones.items():
            if any(self._engine.cards[i].matches(facet, **attrs) for i in ids):
                return name
        return None

    def var(self, name: str) -> Any:
        return self._state.vars[name]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        variables = self._state.vars
        if name in variables:
            return variables[name]
        if f"{name}[0]" in variables:
            return [variables[f"{name}[{p}]"] for p in range(self._engine.n)]
        raise AttributeError(name)
