"""Exact combinatorial belief for games whose unseen cards are EXCHANGEABLE
(probability.md §6.5, Game.exchangeable).

When every unseen card can be swapped with any other unseen card (of the same
visible class, e.g. the same back color) without changing anything the observer
has seen, every assignment of unseen cards to unseen slots is equally likely
(A1 with a uniform shuffle, A1.1). The belief is then fully described by:

    pinned cards  — cards the observer has fully seen, whose location is known;
    slots         — per zone and class, how many unseen cards it holds;
    pool          — per class, the multiset of unseen card types.

Probabilities follow from (multivariate) hypergeometric counting, exactly, with
Fractions — no enumeration of the (possibly ~10^12) worlds.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
from math import comb
from typing import Callable

from ..core.card import FACE, CardType
from ..core.engine import Engine
from ..core.state import State

Match = Callable[[CardType], bool]


def visible_class(engine: Engine, card_type: CardType) -> tuple:
    """Everything about a card except its face: unseen cards can only be swapped
    within the same class (e.g. the same back color)."""
    return card_type.restrict(engine.all_facets - {FACE})


class ExchangeableBelief:
    """Same reading API as WorldsBelief (joker/probability/views.py)."""

    exact = True

    def __init__(self, engine: Engine, world: State, pinned: frozenset[int], observer) -> None:
        self.engine = engine
        self.world = world
        self.observer = observer
        self.known: dict[str, Counter] = defaultdict(Counter)
        self.slots: dict[str, Counter] = defaultdict(Counter)      # zone -> class -> unseen count
        self.pool: dict[tuple, Counter] = defaultdict(Counter)     # class -> unseen types
        self.size: Counter = Counter()                             # class -> unseen cards
        self._known_order: dict[str, list[CardType]] = {}
        for zone, ids in world.zones.items():
            order = []
            for cid in ids:
                t = engine.cards[cid].type
                if cid in pinned:
                    self.known[zone][t] += 1
                    order.append(t)
                else:
                    cls = visible_class(engine, t)
                    self.slots[zone][cls] += 1
                    self.pool[cls][t] += 1
                    self.size[cls] += 1
            self._known_order[zone] = order

    @property
    def support(self) -> int:
        """Number of distinct possible worlds (assignments of unseen cards)."""
        total = 1
        for cls, n in self.size.items():
            remaining = n
            for zone in self.slots:
                k = self.slots[zone][cls]
                total *= comb(remaining, k)
                remaining -= k
        return total

    # --- reading API -------------------------------------------------------------------

    def zone_count(self, zone: str) -> int:
        return len(self.world.zones[zone])

    def known_cards(self, zone: str) -> list[CardType]:
        """Cards certainly in `zone` (pinned, plus unseen cards forced there)."""
        out = list(self._known_order[zone])
        for t in self.pool_types():
            out.extend([t] * (self.certain(zone, t) - self.known[zone][t]))
        return out

    def pool_types(self) -> list[CardType]:
        return [t for cls in self.pool for t in self.pool[cls]]

    def expected(self, zone: str, card_type: CardType) -> Fraction:
        cls = visible_class(self.engine, card_type)
        n = self.size[cls]
        unseen = Fraction(self.pool[cls][card_type] * self.slots[zone][cls], n) if n else Fraction(0)
        return self.known[zone][card_type] + unseen

    def certain(self, zone: str, card_type: CardType) -> int:
        cls = visible_class(self.engine, card_type)
        elsewhere = self.size[cls] - self.slots[zone][cls]
        return self.known[zone][card_type] + max(0, self.pool[cls][card_type] - elsewhere)

    def expected_matching(self, zone: str, match: Match) -> Fraction:
        total = Fraction(sum(n for t, n in self.known[zone].items() if match(t)))
        for cls, types in self.pool.items():
            k = sum(n for t, n in types.items() if match(t))
            if self.size[cls]:
                total += Fraction(k * self.slots[zone][cls], self.size[cls])
        return total

    def prob_at_least(self, zone: str, k: int, match: Match) -> Fraction:
        """P(zone holds at least k cards satisfying `match`) — hypergeometric per class,
        convolved across classes."""
        dist = {sum(n for t, n in self.known[zone].items() if match(t)): Fraction(1)}
        for cls, types in self.pool.items():
            n_total = self.size[cls]
            draws = self.slots[zone][cls]
            if not draws:
                continue
            good = sum(n for t, n in types.items() if match(t))
            pmf = {x: Fraction(comb(good, x) * comb(n_total - good, draws - x), comb(n_total, draws))
                   for x in range(max(0, draws - (n_total - good)), min(good, draws) + 1)}
            new: dict[int, Fraction] = defaultdict(Fraction)
            for a, pa in dist.items():
                for b, pb in pmf.items():
                    new[a + b] += pa * pb
            dist = new
        return sum((p for x, p in dist.items() if x >= k), Fraction(0))

    def public_var(self, name: str):
        var = self.engine.vars[name]
        from ..core.spec import selector_matches
        if selector_matches(var.visible, self.observer, var.owner):
            return self.world.vars[name]
        return None
