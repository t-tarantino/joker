"""Two-player Briscola (see docs/architecture/examples/mini-briscola.md)."""

from __future__ import annotations

from ..cards.classic import italian_40
from ..core import (ALL, BACK, END_HAND, FACE, OTHERS, OWNER, AutoPhase, ChoicePhase, Game, Var,
                    Zone, option, per_player)

ORDER = ("A", "3", "K", "Q", "J", "7", "6", "5", "4", "2")     # strongest first
POINTS = {"A": 11, "3": 10, "K": 4, "Q": 3, "J": 2}


def beats(led, other, trump: str) -> bool:
    """True if the led card wins the trick against `other`."""
    if other.face["suit"] == led.face["suit"]:
        return ORDER.index(led.face["rank"]) < ORDER.index(other.face["rank"])
    return other.face["suit"] != trump


class Deal(AutoPhase):
    def run(self, s, ctx):
        first = 1 - s.dealer
        for p in (first, s.dealer):
            ctx.draw_random("stock", f"hand{p}", n=3)
        ctx.draw_random("stock", "trump_card", n=1)
        ctx.set("leader", first)
        return "set_trump"


class SetTrump(AutoPhase):
    def run(self, s, ctx):
        ctx.set("trump_suit", s.cards("trump_card")[0].face["suit"])
        ctx.set("to_play", s.leader)
        return "play"


class Play(ChoicePhase):
    rules = ()                                      # no obligation to follow suit

    def actors(self, s):
        return [s.to_play]

    def options(self, s, p):
        return [option("play", ref) for ref in s.card_refs(f"hand{p}", seen_by=p)]

    def apply(self, s, joint, ctx):
        (p, opt), = joint.items()
        ctx.move(opt.card, to="table")
        if ctx.state.count("table") == 1:
            ctx.set("to_play", 1 - p)
            return "play"
        return "resolve_trick"


class ResolveTrick(AutoPhase):
    def run(self, s, ctx):
        led, other = s.cards("table")
        w = s.leader if beats(led, other, s.trump_suit) else 1 - s.leader
        for c in (led, other):
            ctx.move(c, to=f"won{w}")
        ctx.set("leader", w)
        ctx.set("to_play", w)
        n = s.count("stock")
        if n >= 2:
            ctx.draw_random("stock", f"hand{w}")
            ctx.draw_random("stock", f"hand{1 - w}")
        elif n == 1:
            ctx.draw_random("stock", f"hand{w}")
            ctx.move(s.cards("trump_card")[0], to=f"hand{1 - w}")
        if n == 0 and s.count(f"hand{w}") == 0:
            return END_HAND
        return "play"


class Briscola2(Game):
    name = "briscola-2p"
    players = 2
    deck = italian_40(back_color="blue")
    zones = (
        Zone("stock", facets={ALL: set()}),
        Zone("trump_card", facets={ALL: {BACK, FACE}}),
        per_player(lambda p: Zone(f"hand{p}", owner=p, facets={OWNER: {BACK, FACE}, OTHERS: {BACK}})),
        Zone("table", ordered=True, facets={ALL: {BACK, FACE}}),
        per_player(lambda p: Zone(f"won{p}", owner=p, facets={ALL: {BACK}})),
    )
    match_vars = (Var("dealer", initial=0), Var("hands_won", initial=0, per_player=True))
    hand_vars = (Var("trump_suit"), Var("leader"), Var("to_play"))
    phases = {"deal": Deal(), "set_trump": SetTrump(), "play": Play(),
              "resolve_trick": ResolveTrick()}
    initial_phase = "deal"

    def end_hand(self, s, ctx):
        points = [sum(POINTS.get(c.face["rank"], 0) for c in s.cards(f"won{p}")) for p in (0, 1)]
        for p in (0, 1):
            if points[p] > 60:
                ctx.set(f"hands_won[{p}]", s.hands_won[p] + 1)
        ctx.set("dealer", 1 - s.dealer)
