"""Tiny games for tests — small enough for the brute-force oracle.

- TinyTricks:  6 cards, follow-suit rule of class LATER (void inference, violations).
- TinyDiscard: two back colors + a face-down discard (partially observed choice, S1.6).
- TinyDupDiscard: duplicate copies + a hidden discard (option canonicalization, S7.8).
- TinyFollow:  the A1.1 example (7 of spades) as a playable game.
- TinyCarry:   cards that stay out between hands (match-level zones, Engine.next_hand).
"""

from __future__ import annotations

from ..core import (ALL, BACK, END_HAND, FACE, LATER, OTHERS, OWNER, AutoPhase, CardType,
                    ChoicePhase, Game, Rule, Var, Zone, option, per_player)


def _hands():
    return per_player(lambda p: Zone(f"hand{p}", owner=p, facets={OWNER: {BACK, FACE}, OTHERS: {BACK}}))


def _follow_suit(s, p, opt) -> bool:
    table = s.cards("table")
    if not table:
        return True
    led = table[0].face["suit"]
    if opt.card.face["suit"] == led:
        return True
    return not any(c.face["suit"] == led for c in s.cards(f"hand{p}"))


FOLLOW_SUIT = Rule("follow_suit", LATER, _follow_suit)


class _PlayCard(ChoicePhase):
    """The player `to_play` plays one card of their hand to the table."""

    rules = (FOLLOW_SUIT,)

    def __init__(self, next_phase: str, after_two: str) -> None:
        self.next_phase = next_phase
        self.after_two = after_two

    def actors(self, s):
        return [s.to_play]

    def options(self, s, p):
        return [option("play", ref) for ref in s.card_refs(f"hand{p}", seen_by=p)]

    def apply(self, s, joint, ctx):
        (p, opt), = joint.items()
        ctx.move(opt.card, to="table")
        if ctx.state.count("table") == 1:
            ctx.set("to_play", 1 - p)
            return self.next_phase
        return self.after_two


# --- TinyTricks ---------------------------------------------------------------------

class _TricksDeal(AutoPhase):
    def run(self, s, ctx):
        ctx.draw_random("stock", "hand0", n=2)
        ctx.draw_random("stock", "hand1", n=2)
        ctx.set("to_play", s.leader)
        return "play"


class _TricksResolve(AutoPhase):
    def run(self, s, ctx):
        led, other = s.cards("table")
        leader_wins = other.face["suit"] != led.face["suit"] or led.face["rank"] > other.face["rank"]
        w = s.leader if leader_wins else 1 - s.leader
        for c in (led, other):
            ctx.move(c, to="won")
        ctx.set("leader", w)
        ctx.set("to_play", w)
        if s.count("stock") >= 2:
            ctx.draw_random("stock", f"hand{w}")
            ctx.draw_random("stock", f"hand{1 - w}")
        if s.count("stock") == 0 and s.count(f"hand{w}") == 0:
            return END_HAND
        return "play"


class TinyTricks(Game):
    name = "tiny-tricks"
    players = 2
    deck = [(CardType.of(back={"color": "blue"}, face={"suit": suit, "rank": rank}), 1)
            for suit in ("a", "b") for rank in (1, 2, 3)]
    zones = (Zone("stock", facets={ALL: set()}), _hands(),
             Zone("table", ordered=True, facets={ALL: {BACK, FACE}}),
             Zone("won", facets={ALL: {BACK}}))
    hand_vars = (Var("leader", initial=0), Var("to_play", initial=0))
    phases = {"deal": _TricksDeal(), "play": _PlayCard("play", "resolve"),
              "resolve": _TricksResolve()}
    initial_phase = "deal"


# --- TinyDiscard / TinyDupDiscard ----------------------------------------------------------

class _DiscardDeal(AutoPhase):
    def __init__(self, to_hand0: int, to_hand1: int) -> None:
        self.to_hand0 = to_hand0
        self.to_hand1 = to_hand1

    def run(self, s, ctx):
        if self.to_hand0:
            ctx.draw_random("stock", "hand0", n=self.to_hand0)
        ctx.draw_random("stock", "hand1", n=self.to_hand1)
        return "discard"


class _Discard(ChoicePhase):
    """Player 1 discards one card face down (back visible to everyone)."""

    def actors(self, s):
        return [1]

    def options(self, s, p):
        return [option("discard", ref) for ref in s.card_refs("hand1", seen_by=1)]

    def apply(self, s, joint, ctx):
        ctx.move(joint[1].card, to="discard")
        return END_HAND


class TinyDiscard(Game):
    name = "tiny-discard"
    players = 2
    deck = [(CardType.of(back={"color": color}, face={"rank": rank}), 1)
            for color in ("red", "blue") for rank in (1, 2, 3)]
    zones = (Zone("stock", facets={ALL: set()}), _hands(),
             Zone("discard", facets={ALL: {BACK}}))
    phases = {"deal": _DiscardDeal(2, 2), "discard": _Discard()}
    initial_phase = "deal"


class TinyDupDiscard(Game):
    """Deck {1, 1, 2, 3} (two identical 1s). Player 1 gets 3 cards and discards one
    face down. S7.8 predicts P(discarded card is a 1) = 5/12 for an outside observer."""

    name = "tiny-dup-discard"
    players = 2
    deck = [(CardType.of(back={"color": "blue"}, face={"rank": 1}), 2),
            (CardType.of(back={"color": "blue"}, face={"rank": 2}), 1),
            (CardType.of(back={"color": "blue"}, face={"rank": 3}), 1)]
    zones = TinyDiscard.zones
    phases = {"deal": _DiscardDeal(0, 3), "discard": _Discard()}
    initial_phase = "deal"


# --- TinyFollow: the A1.1 example --------------------------------------------------------

class _FollowDeal(AutoPhase):
    def run(self, s, ctx):
        ctx.draw_random("stock", "hand0", n=1)
        ctx.draw_random("stock", "hand1", n=2)
        ctx.set("to_play", 0)
        return "play"


class _Done(AutoPhase):
    def run(self, s, ctx):
        return END_HAND


class TinyFollow(Game):
    """Deck {2♠, 7♠, K♠, 3♥}. Player 0 gets 1 card, player 1 gets 2, one stays in the
    stock. Player 0 leads, player 1 must follow suit (class LATER)."""

    name = "tiny-follow"
    players = 2
    deck = [(CardType.of(back={"color": "blue"}, face={"suit": suit, "rank": rank}), 1)
            for suit, rank in (("spades", "2"), ("spades", "7"), ("spades", "K"), ("hearts", "3"))]
    zones = (Zone("stock", facets={ALL: set()}), _hands(),
             Zone("table", ordered=True, facets={ALL: {BACK, FACE}}))
    hand_vars = (Var("leader", initial=0), Var("to_play", initial=0))
    phases = {"deal": _FollowDeal(), "play": _PlayCard("play", "done"), "done": _Done()}
    initial_phase = "deal"


# --- TinyCarry: cards that stay out between hands ---------------------------------------------

class _CarryDeal(AutoPhase):
    def run(self, s, ctx):
        ctx.draw_random("stock", "up")
        ctx.draw_random("stock", "down")
        return "ask"


class _CarryAsk(ChoicePhase):
    """Player 0 may ask whether the face-down card is high (rank >= 3): public answer."""

    def actors(self, s):
        return [0]

    def options(self, s, p):
        return [option("ask"), option("pass")]

    def apply(self, s, joint, ctx):
        if joint[0].kind == "ask":
            ctx.set("high", s.cards("down")[0].face["rank"] >= 3)
        return END_HAND


class TinyCarry(Game):
    """Deck {1, 1, 2, 3, 4}. Each hand: one card face up, one face down; the cards
    then go to a face-down discard that stays out for the next hand (match-level
    zones). The face-down card is never shown, so it carries unseen information."""

    name = "tiny-carry"
    players = 1
    deck = [(CardType.of(back={"color": "blue"}, face={"rank": r}), n)
            for r, n in ((1, 2), (2, 1), (3, 1), (4, 1))]
    zones = (Zone("stock", facets={ALL: set()}, match_level=True),
             Zone("discard", facets={ALL: set()}, match_level=True),
             Zone("up", facets={ALL: {BACK, FACE}}),
             Zone("down", facets={ALL: {BACK}}))
    hand_vars = (Var("high", initial=None),)
    phases = {"deal": _CarryDeal(), "ask": _CarryAsk()}
    initial_phase = "deal"

    def end_hand(self, s, ctx):
        for zone in ("up", "down"):
            for card in s.cards(zone):
                ctx.move(card, to="discard")
