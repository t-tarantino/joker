"""Classic suited decks — the Goal 1 card library (S1.2a).

Italian and French families, with optional jokers. Which cards and how many copies
a game uses is decided by the game: use `subset` and `union` to build it.
"""

from __future__ import annotations

from typing import Iterable

from ..core.card import CardType, DeckSpec

ITALIAN_SUITS = ("cups", "coins", "clubs", "swords")             # coppe, denari, bastoni, spade
ITALIAN_RANKS = ("A", "2", "3", "4", "5", "6", "7", "J", "Q", "K")  # J = fante, Q = queen (cavallo), K = re

FRENCH_SUITS = ("hearts", "diamonds", "clubs", "spades")
FRENCH_RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")

JOKER = "JOKER"


def _card(suit: str | None, rank: str, back_color: str) -> CardType:
    return CardType.of(back={"color": back_color}, face={"suit": suit, "rank": rank})


def italian_40(back_color: str = "blue") -> DeckSpec:
    return [(_card(s, r, back_color), 1) for s in ITALIAN_SUITS for r in ITALIAN_RANKS]


def french_52(jokers: int = 0, back_color: str = "red") -> DeckSpec:
    deck = [(_card(s, r, back_color), 1) for s in FRENCH_SUITS for r in FRENCH_RANKS]
    if jokers:
        deck.append((_card(None, JOKER, back_color), jokers))
    return deck


def subset(deck: DeckSpec, ranks: Iterable[str] | None = None,
           suits: Iterable[str] | None = None) -> DeckSpec:
    """Keep only the given ranks / suits (e.g. a 32-card piquet deck)."""
    ranks = None if ranks is None else set(ranks)
    suits = None if suits is None else set(suits)
    return [(t, n) for t, n in deck
            if (ranks is None or t.face["rank"] in ranks)
            and (suits is None or t.face["suit"] in suits)]


def union(*decks: DeckSpec) -> DeckSpec:
    """Combine decks; identical card types add up their copies (S1.1)."""
    counts: dict[CardType, int] = {}
    for deck in decks:
        for card_type, n in deck:
            counts[card_type] = counts.get(card_type, 0) + n
    return list(counts.items())
