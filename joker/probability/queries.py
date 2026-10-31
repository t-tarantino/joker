"""Queries on possible worlds (probability.md §4). Queries are written on card
attributes and derived functions, never on internal card ids (S1.1b).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Callable

from ..core.card import FACE, FrozenAttrs

if TYPE_CHECKING:
    from ..core.engine import Engine
    from ..core.state import View

Worlds = list[tuple["View", Fraction]]   # normalized: weights sum to 1


class Query:
    def evaluate(self, engine: Engine, worlds: Worlds) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class P(Query):
    """Probability that a predicate holds, e.g. P(lambda w: w.holds("hand1", rank="A"))."""

    predicate: Callable[[View], bool]

    def evaluate(self, engine: Engine, worlds: Worlds) -> Fraction:
        return sum((w for view, w in worlds if self.predicate(view)), Fraction(0))


@dataclass(frozen=True)
class Distribution(Query):
    """Distribution of any function of the world: a hidden variable, a derived role, ..."""

    fn: Callable[[View], Any]

    def evaluate(self, engine: Engine, worlds: Worlds) -> dict[Any, Fraction]:
        out: dict[Any, Fraction] = defaultdict(Fraction)
        for view, w in worlds:
            out[self.fn(view)] += w
        return dict(out)


@dataclass(frozen=True)
class Marginals(Query):
    """Expected number of copies of each card face in `zone` (= probability when the
    deck has one copy per face)."""

    zone: str

    def evaluate(self, engine: Engine, worlds: Worlds) -> dict[FrozenAttrs, Fraction]:
        out: dict[FrozenAttrs, Fraction] = defaultdict(Fraction)
        for view, w in worlds:
            for card in view.cards(self.zone):
                out[_face_key(card.type)] += w
        return dict(out)


@dataclass(frozen=True)
class NextDraw(Query):
    """Distribution of the face of the next card drawn uniformly from `src`. Pure Nature
    lookahead: valid only if no player choice happens before that draw (A0)."""

    src: str

    def evaluate(self, engine: Engine, worlds: Worlds) -> dict[FrozenAttrs, Fraction]:
        out: dict[FrozenAttrs, Fraction] = defaultdict(Fraction)
        for view, w in worlds:
            cards = view.cards(self.src)
            for card in cards:
                out[_face_key(card.type)] += w / len(cards)
        return dict(out)


def _face_key(card_type) -> FrozenAttrs:
    return tuple(sorted(card_type.facet(FACE).items(), key=lambda kv: kv[0]))
