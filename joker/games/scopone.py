"""Scopone scientifico — 4 players in two teams (0 & 2 vs 1 & 3), Italian 40-card
deck, 10 cards each, table empty at the start, play goes to the next seat (p + 1).

Captures: a played card must capture a table card of the same rank if there is
one (choosing which, if several); otherwise it must capture a set of table cards
whose values add up to its value (choosing which set, if several); otherwise it
stays on the table. Values: A=1 … 7=7, J=8, Q=9, K=10. Clearing the table is a
"scopa" (+1), except with the very last card of the hand. At the end the cards left
on the table go to the team that captured last.

`make_scopone(...)` builds smaller variants (used by tests to check the exact
combinatorial method against full enumeration).
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

from ..cards.classic import ITALIAN_RANKS, ITALIAN_SUITS, italian_40, subset
from ..core import (ALL, BACK, END_HAND, FACE, OTHERS, OWNER, AutoPhase, ChoicePhase, Game, Var,
                    Zone, option, per_player)

VALUES = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "J": 8, "Q": 9, "K": 10}
PRIMIERA = {"7": 21, "6": 18, "A": 16, "5": 15, "4": 14, "3": 13, "2": 12, "J": 10, "Q": 10, "K": 10}


def team_of(player: int) -> int:
    return player % 2


def capture_sets(value: int, table: list) -> list[tuple]:
    """Every set of table cards the played value may capture (empty list: none)."""
    same = [c for c in table if VALUES[c.face["rank"]] == value]
    if same:
        return [(c,) for c in same]
    return [combo for size in range(2, len(table) + 1) for combo in combinations(table, size)
            if sum(VALUES[c.face["rank"]] for c in combo) == value]


class Deal(AutoPhase):
    def __init__(self, hand_size: int) -> None:
        self.hand_size = hand_size

    def run(self, s, ctx):
        first = (s.dealer + 1) % 4
        for k in range(4):
            ctx.draw_random("stock", f"hand{(first + k) % 4}", n=self.hand_size)
        ctx.set("to_play", first)
        return "play"


class Play(ChoicePhase):
    rules = ()                      # capture obligations are physical: they are in `options`

    def actors(self, s):
        return [s.to_play]

    def options(self, s, p):
        table = s.cards("table")
        out = []
        for ref in s.card_refs(f"hand{p}", seen_by=p):
            sets = capture_sets(VALUES[ref.face["rank"]], table)
            if not sets:
                out.append(option("play", ref, ()))
            for combo in sets:
                out.append(option("play", ref, tuple(s.ref_of(c, p) for c in combo)))
        return out

    def apply(self, s, joint, ctx):
        (p, opt), = joint.items()
        ref, captures = opt.args
        played = ctx.move(ref, to="table")
        if captures:
            team = team_of(p)
            for c in captures:
                ctx.move(c, to=f"taken{team}")
            ctx.move(played, to=f"taken{team}")
            ctx.set("last_taker", p)
            last_card = all(ctx.state.count(f"hand{q}") == 0 for q in range(4))
            if ctx.state.count("table") == 0 and not last_card:
                ctx.set(f"scope{team}", s.var(f"scope{team}") + 1)
        if all(ctx.state.count(f"hand{q}") == 0 for q in range(4)):
            return "end"
        ctx.set("to_play", (p + 1) % 4)
        return "play"


class EndHand(AutoPhase):
    def run(self, s, ctx):
        if s.last_taker is not None:
            for c in s.cards("table"):
                ctx.move(c, to=f"taken{team_of(s.last_taker)}")
        return END_HAND


def make_scopone(suits=ITALIAN_SUITS, ranks=ITALIAN_RANKS, hand_size: int = 10) -> Game:
    deck = subset(italian_40(back_color="blue"), ranks=ranks, suits=suits)
    if len(deck) != 4 * hand_size:
        raise ValueError("the deck must be dealt completely: 4 x hand_size cards")

    class Scopone(Game):
        name = "scopone-scientifico" if hand_size == 10 else f"scopone-{len(deck)}"
        players = 4
        exchangeable = True        # every play is face up and every capture is public
        zones = (
            Zone("stock", facets={ALL: set()}),
            per_player(lambda p: Zone(f"hand{p}", owner=p, facets={OWNER: {BACK, FACE}, OTHERS: {BACK}})),
            Zone("table", facets={ALL: {BACK, FACE}}),
            Zone("taken0", facets={ALL: {BACK}}),
            Zone("taken1", facets={ALL: {BACK}}),
        )
        match_vars = (Var("dealer", initial=3),)
        hand_vars = (Var("to_play"), Var("last_taker"), Var("scope0", initial=0), Var("scope1", initial=0))
        phases = {"deal": Deal(hand_size), "play": Play(), "end": EndHand()}
        initial_phase = "deal"

    Scopone.deck = deck
    return Scopone()


def hand_score(taken: dict[int, list], scope: dict[int, int]) -> dict:
    """Points of one hand for each team. `taken[team]` = list of card faces."""
    def primiera(faces):
        best = {}
        for f in faces:
            best[f["suit"]] = max(best.get(f["suit"], 0), PRIMIERA[f["rank"]])
        return sum(best.values()) if len(best) == 4 else 0

    detail = {0: {}, 1: {}}
    cards = {t: len(taken[t]) for t in (0, 1)}
    coins = {t: sum(1 for f in taken[t] if f["suit"] == "coins") for t in (0, 1)}
    prim = {t: primiera(taken[t]) for t in (0, 1)}
    for t in (0, 1):
        o = 1 - t
        detail[t]["cards"] = int(cards[t] > cards[o])
        detail[t]["coins"] = int(coins[t] > coins[o])
        detail[t]["settebello"] = int(any(f == {"suit": "coins", "rank": "7"} for f in taken[t]))
        detail[t]["primiera"] = int(prim[t] > prim[o])
        detail[t]["scope"] = scope[t]
        detail[t]["total"] = sum(detail[t].values())
    return detail


ScoponeScientifico = make_scopone
