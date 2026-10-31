"""A common reading API over beliefs, so presentation code (the GUI) does not care
which method produced them. Implemented by WorldsBelief (explicit possible worlds)
and ExchangeableBelief (combinatorial, joker/probability/exchangeable.py).

Every method returns an AGGREGATE over possible worlds, never one world (S5.4).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
from typing import Callable

from ..core.card import CardType
from ..core.engine import Engine
from ..core.state import View

Match = Callable[[CardType], bool]


class WorldsBelief:
    exact = True

    def __init__(self, engine: Engine, worlds: list[tuple[View, Fraction]]) -> None:
        self.engine = engine
        self.worlds = worlds
        self._expected: dict[str, dict] = defaultdict(lambda: defaultdict(Fraction))
        self._certain: dict[str, dict] = {}
        for view, w in worlds:
            for zone, ids in view.raw.zones.items():
                counts = Counter(engine.cards[i].type for i in ids)
                for t, n in counts.items():
                    self._expected[zone][t] += w * n
                if zone not in self._certain:
                    self._certain[zone] = dict(counts)
                else:
                    self._certain[zone] = {t: min(n, counts.get(t, 0))
                                           for t, n in self._certain[zone].items() if counts.get(t, 0)}

    @property
    def support(self) -> int:
        return len(self.worlds)

    def zone_count(self, zone: str) -> int:
        return len(self.worlds[0][0].raw.zones[zone])          # counts are public (S1.5)

    def known_cards(self, zone: str) -> list[CardType]:
        if self.engine.zones[zone].ordered:                     # keep play order when fully known
            ids = self.worlds[0][0].raw.zones[zone]
            types = [self.engine.cards[i].type for i in ids]
            if all(self.certain(zone, t) >= types.count(t) for t in types):
                return types
        return [t for t, n in self._certain.get(zone, {}).items() for _ in range(n)]

    def expected(self, zone: str, card_type: CardType) -> Fraction:
        return self._expected[zone][card_type]

    def certain(self, zone: str, card_type: CardType) -> int:
        return self._certain.get(zone, {}).get(card_type, 0)

    def expected_matching(self, zone: str, match: Match) -> Fraction:
        return sum((n for t, n in self._expected[zone].items() if match(t)), Fraction(0))

    def prob_at_least(self, zone: str, k: int, match: Match) -> Fraction:
        return sum((w for view, w in self.worlds
                    if sum(1 for c in view.cards(zone) if match(c.type)) >= k), Fraction(0))

    def public_var(self, name: str):
        values = {view.raw.vars[name] for view, _ in self.worlds}
        return values.pop() if len(values) == 1 else None
