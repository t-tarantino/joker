"""Cards, facets and decks.

Implements assumptions S1.1 (the deck is a multiset), S1.1b (copy labels are
never observable), S1.2 (free-form attributes) and S1.6 (attributes grouped
into facets).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

Facet = str
BACK: Facet = "back"
FACE: Facet = "face"

FrozenAttrs = tuple[tuple[str, Any], ...]
FrozenFacets = tuple[tuple[Facet, FrozenAttrs], ...]


def freeze_facets(facets: Mapping[Facet, Mapping[str, Any]]) -> FrozenFacets:
    """Canonical, hashable form of {facet: {attr: value}}. Values must be hashable."""
    return tuple(
        (name, tuple(sorted(attrs.items(), key=lambda kv: kv[0])))
        for name, attrs in sorted(facets.items(), key=lambda kv: kv[0])
    )


def facet_dict(facets: FrozenFacets, name: Facet) -> dict[str, Any]:
    """Attributes of one facet as a dict (empty if the facet is absent or hidden)."""
    for facet, attrs in facets:
        if facet == name:
            return dict(attrs)
    return {}


def describe(facets: FrozenFacets) -> str:
    """Human-readable form, e.g. 'back(color=blue) face(rank=A, suit=coins)'."""
    parts = [f"{facet}(" + ", ".join(f"{k}={v}" for k, v in attrs) + ")" for facet, attrs in facets]
    return " ".join(parts) if parts else "<nothing visible>"


@dataclass(frozen=True)
class CardType:
    """What a card *is*: its attributes, grouped by facet."""

    facets: FrozenFacets

    @staticmethod
    def of(**facets: Mapping[str, Any]) -> CardType:
        """CardType.of(back={"color": "blue"}, face={"suit": "coins", "rank": "A"})"""
        return CardType(freeze_facets(facets))

    def facet(self, name: Facet) -> dict[str, Any]:
        return facet_dict(self.facets, name)

    @property
    def face(self) -> dict[str, Any]:
        return self.facet(FACE)

    @property
    def back(self) -> dict[str, Any]:
        return self.facet(BACK)

    @property
    def facet_names(self) -> frozenset[Facet]:
        return frozenset(f for f, _ in self.facets)

    def restrict(self, visible: frozenset[Facet]) -> FrozenFacets:
        """Only the facets in `visible` — what an observer can actually see."""
        return tuple(item for item in self.facets if item[0] in visible)

    def matches(self, facet: Facet = FACE, **attrs: Any) -> bool:
        values = self.facet(facet)
        return all(values.get(k) == v for k, v in attrs.items())

    def __str__(self) -> str:
        return describe(self.facets)


DeckSpec = list[tuple[CardType, int]]
"""A multiset of card types: [(type, number of copies), ...] (S1.1)."""


@dataclass(frozen=True)
class Card:
    """One physical copy. `id` is an internal label, never observable (S1.1b)."""

    id: int
    type: CardType

    @property
    def face(self) -> dict[str, Any]:
        return self.type.face

    @property
    def back(self) -> dict[str, Any]:
        return self.type.back

    def matches(self, facet: Facet = FACE, **attrs: Any) -> bool:
        return self.type.matches(facet, **attrs)

    def __str__(self) -> str:
        return f"#{self.id} {self.type}"


def build_cards(deck: Iterable[tuple[CardType, int]]) -> tuple[Card, ...]:
    """Give every physical copy its internal id (0..n-1, in deck order)."""
    cards: list[Card] = []
    for card_type, copies in deck:
        if copies < 1:
            raise ValueError(f"deck entry {card_type} has {copies} copies")
        for _ in range(copies):
            cards.append(Card(len(cards), card_type))
    return tuple(cards)
