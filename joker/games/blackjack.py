"""Blackjack, one player against the dealer (ROADMAP rung 1).

The dealer follows a fixed procedure, so the only decision maker is the player:
the "opponent" is part of the rules (AutoPhases), not a thinking player.

Modeling choices (all exact for the rules as written):
- Suits never matter in blackjack, and 10, J, Q, K behave identically (any two
  ten-valued cards may be split), so the deck lists only ranks A, 2..9, T, with
  16 T per deck. Every probability is unchanged.
- Lazy draws (DR-2). The dealer's hole card is drawn at the start only when the
  up card is an Ace or a ten (the dealer must peek for blackjack); otherwise it
  is drawn when the dealer reveals it. Unseen, it is exchangeable with the shoe,
  so the distribution of everything the player sees is the same.
- The dealer peeks (US rules): with a dealer blackjack the hand ends at once and
  only the original bet is lost. The no-hole-card variant is not modeled yet.
- A hand totalling 21 stands automatically (hitting it can never help).
- After a split, hands are played in order: hand 0, 1, 2, ...; a split hand gets
  its second card only when its turn comes, as at the table.
- Several hands from the same shoe (card counting): `shoe` and `discard` are
  match-level zones. Between hands (Engine.next_hand, Game.end_hand) every card on
  the table goes to the discard tray, face down; after the hand that reaches the
  cut card (`penetration`) the discard goes back into the shoe. If the shoe runs
  out during a hand, it refills from the discard tray one random card at a time
  (the same as shuffling the discards). An undrawn hole card (lazy draw) stays in
  the shoe: every later card has the same odds; only the cut card comes one card
  later than at the table.

The result of the hand, in units of the original bet, is the variable `net`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..core import ALL, BACK, END_HAND, FACE, AutoPhase, CardType, ChoicePhase, Game, Var, Zone, option

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T")
ACTIONS = ("stand", "hit", "double", "split")


@dataclass(frozen=True)
class BlackjackRules:
    """A rule set. Defaults: one deck, dealer stands on soft 17, double on any two
    cards and after splits, split up to 4 hands, aces split once with one card each,
    blackjack pays 3 to 2."""

    decks: int | None = 1               # None = infinite deck (exact solver only)
    hit_soft_17: bool = False           # dealer hits soft 17 ("H17") or stands ("S17")
    double: str = "any"                 # "any" two cards, "9-11", "10-11" or "none"
    double_after_split: bool = True     # "DAS"
    max_hands: int = 4                  # 1 = no splitting, 2 = split once, 4 = resplit to 4
    resplit_aces: bool = False
    hit_split_aces: bool = False        # False: split aces get one card each
    blackjack_pays: Fraction = Fraction(3, 2)
    # Cut card, used only when hands follow each other from the same shoe
    # (Engine.next_hand): reshuffle after the hand in which this fraction of the
    # shoe was dealt. None = only when told (live mode: the person says when).
    penetration: Fraction | None = Fraction(3, 4)

    def describe(self) -> str:
        decks = "infinite deck" if self.decks is None else f"{self.decks} deck{'s' * (self.decks > 1)}"
        parts = [decks, "H17" if self.hit_soft_17 else "S17", f"double {self.double}",
                 "DAS" if self.double_after_split else "no DAS",
                 "no splitting" if self.max_hands == 1 else f"split to {self.max_hands} hands",
                 "resplit aces" if self.resplit_aces else "no resplit aces",
                 "hit split aces" if self.hit_split_aces else "one card on split aces",
                 f"blackjack pays {self.blackjack_pays}", "dealer peeks"]
        if self.penetration is not None:
            parts.append(f"reshuffle at {float(self.penetration):.0%} of the shoe")
        return ", ".join(parts)


# --- hand arithmetic (shared with the exact solver) ------------------------------------

def card_value(rank: str) -> int:
    return 1 if rank == "A" else 10 if rank == "T" else int(rank)


def hand_value(ranks) -> tuple[int, bool]:
    """(best total, soft?). Soft = an ace counts 11 without busting."""
    total = sum(card_value(r) for r in ranks)
    if "A" in ranks and total + 10 <= 21:
        return total + 10, True
    return total, False


def is_blackjack(ranks) -> bool:
    return len(ranks) == 2 and hand_value(ranks)[0] == 21


def dealer_stands(ranks, rules: BlackjackRules) -> bool:
    total, soft = hand_value(ranks)
    return total > 17 or (total == 17 and not (soft and rules.hit_soft_17))


def legal_actions(rules: BlackjackRules, ranks, n_hands: int, split_aces: bool) -> tuple[str, ...]:
    """The player's options for one hand. Empty or ("stand",) = the hand is over."""
    total, _ = hand_value(ranks)
    if total >= 21:
        return ()
    one_card_aces = split_aces and not rules.hit_split_aces
    actions = ["stand"]
    if not one_card_aces:
        actions.append("hit")
    if len(ranks) == 2:
        if not one_card_aces and may_double(rules, total, n_hands):
            actions.append("double")
        if (ranks[0] == ranks[1] and n_hands < rules.max_hands
                and (ranks[0] != "A" or n_hands == 1 or rules.resplit_aces)):
            actions.append("split")
    return tuple(actions)


def may_double(rules: BlackjackRules, total: int, n_hands: int) -> bool:
    if n_hands > 1 and not rules.double_after_split:
        return False
    return {"any": True, "9-11": 9 <= total <= 11, "10-11": 10 <= total <= 11,
            "none": False}[rules.double]


def compare(player_total: int, dealer_total: int) -> int:
    """+1 / 0 / -1 for a player hand that did not bust."""
    if dealer_total > 21 or player_total > dealer_total:
        return 1
    return 0 if player_total == dealer_total else -1


# --- phases -----------------------------------------------------------------------------

def _ranks(s, zone: str) -> tuple[str, ...]:
    return tuple(sorted(c.face["rank"] for c in s.cards(zone)))


def _peeks(up: str) -> bool:
    return up in ("A", "T")


class _Phase:
    def __init__(self, rules: BlackjackRules) -> None:
        self.rules = rules


class Deal(_Phase, AutoPhase):
    def run(self, s, ctx):
        ctx.draw_random("shoe", "hand0")
        ctx.draw_random("shoe", "up")
        ctx.draw_random("shoe", "hand0")
        return "after_deal"


class AfterDeal(_Phase, AutoPhase):
    def run(self, s, ctx):
        if _peeks(_ranks(s, "up")[0]):
            ctx.draw_random("shoe", "hole")
            return "peek"
        return "naturals"


class Peek(_Phase, AutoPhase):
    def run(self, s, ctx):
        if is_blackjack(_ranks(s, "up") + _ranks(s, "hole")):
            ctx.move(s.cards("hole")[0], to="dealer")
            ctx.set("net", Fraction(0) if is_blackjack(_ranks(s, "hand0")) else Fraction(-1))
            return END_HAND
        return "naturals"


class Naturals(_Phase, AutoPhase):
    def run(self, s, ctx):
        if is_blackjack(_ranks(s, "hand0")):
            ctx.set("net", self.rules.blackjack_pays)
            return END_HAND
        return "play"


class Play(ChoicePhase):
    rules = ()          # regulatory rules (A3): none, every option offered is legal

    def __init__(self, game_rules: BlackjackRules) -> None:
        self._rules = game_rules

    def actors(self, s):
        return [0]

    def options(self, s, p):
        h = s.active
        return [option(a) for a in legal_actions(self._rules, _ranks(s, f"hand{h}"), s.n_hands, s.split_aces)]

    def apply(self, s, joint, ctx):
        action = joint[0].kind
        h = s.active
        if action == "stand":
            return "next_hand"
        if action == "hit":
            ctx.draw_random("shoe", f"hand{h}")
            return "check_hand"
        if action == "double":
            bets = list(s.bets)
            bets[h] = 2
            ctx.set("bets", tuple(bets))
            ctx.draw_random("shoe", f"hand{h}")
            return "check_hand"
        n = s.n_hands                                       # split: the new hand is hand n
        ctx.move(s.cards(f"hand{h}")[1], to=f"hand{n}")
        ctx.set("n_hands", n + 1)
        bets = list(s.bets)
        bets[n] = 1
        ctx.set("bets", tuple(bets))
        if s.cards(f"hand{h}")[0].face["rank"] == "A":
            ctx.set("split_aces", True)
        return "check_hand"


class CheckHand(_Phase, AutoPhase):
    """Second card of a split hand; then either the player decides or the hand is over."""

    def run(self, s, ctx):
        h = s.active
        ranks = _ranks(s, f"hand{h}")
        if len(ranks) == 1:
            ctx.draw_random("shoe", f"hand{h}")
            return "check_hand"
        if s.bets[h] == 2 or len(legal_actions(self.rules, ranks, s.n_hands, s.split_aces)) <= 1:
            return "next_hand"
        return "play"


class NextHand(_Phase, AutoPhase):
    def run(self, s, ctx):
        if s.active + 1 < s.n_hands:
            ctx.set("active", s.active + 1)
            return "check_hand"
        return "dealer"


class DealerReveals(_Phase, AutoPhase):
    def run(self, s, ctx):
        hands = [_ranks(s, f"hand{h}") for h in range(s.n_hands)]
        if all(hand_value(r)[0] > 21 for r in hands):
            ctx.set("net", Fraction(-sum(s.bets)))
            return END_HAND
        if s.count("hole"):
            ctx.move(s.cards("hole")[0], to="dealer")
        else:
            ctx.draw_random("shoe", "dealer")
        return "dealer_draws"


class DealerDraws(_Phase, AutoPhase):
    def run(self, s, ctx):
        if dealer_stands(_ranks(s, "up") + _ranks(s, "dealer"), self.rules):
            return "settle"
        ctx.draw_random("shoe", "dealer")
        return "dealer_draws"


class Settle(_Phase, AutoPhase):
    def run(self, s, ctx):
        dealer_total = hand_value(_ranks(s, "up") + _ranks(s, "dealer"))[0]
        net = 0
        for h in range(s.n_hands):
            total = hand_value(_ranks(s, f"hand{h}"))[0]
            net += s.bets[h] * (-1 if total > 21 else compare(total, dealer_total))
        ctx.set("net", Fraction(net))
        return END_HAND


# --- the game --------------------------------------------------------------------------

def shoe_counts(decks: int) -> tuple[int, ...]:
    """Cards per rank A..T in a shoe of `decks` decks."""
    return tuple((16 if r == "T" else 4) * decks for r in RANKS)


class Blackjack(Game):
    """One player (player 0) against the dealer. `shoe` overrides the deck count with
    an explicit number of cards per rank A..T (used for small test shoes)."""

    name = "blackjack"
    players = 1
    deck_zone = "shoe"
    initial_phase = "deal"

    def __init__(self, rules: BlackjackRules = BlackjackRules(), shoe: tuple[int, ...] | None = None) -> None:
        if shoe is None:
            if rules.decks is None:
                raise ValueError("an infinite deck cannot be dealt; use the exact solver")
            shoe = shoe_counts(rules.decks)
        self.rules = rules
        self.shoe = tuple(shoe)
        self.deck = [(CardType.of(back={"color": "red"}, face={"rank": r}), n)
                     for r, n in zip(RANKS, self.shoe) if n > 0]
        visible = {ALL: {BACK, FACE}}
        self.zones = (
            Zone("shoe", facets={ALL: set()}, match_level=True, refill_from="discard"),
            Zone("discard", facets={ALL: set()}, match_level=True),  # face-down tray
            Zone("up", facets=visible),
            Zone("hole", facets={ALL: {BACK}}),                 # face down
            Zone("dealer", facets=visible),                     # revealed hole card + hits
            *(Zone(f"hand{h}", owner=0, facets=visible) for h in range(rules.max_hands)),
        )
        self.hand_vars = (
            Var("n_hands", initial=1),
            Var("active", initial=0),                           # hand being played
            Var("bets", initial=(1,) + (0,) * (rules.max_hands - 1)),
            Var("split_aces", initial=False),
            Var("net", initial=Fraction(0)),                    # result in original bets
        )
        r = rules
        self.phases = {"deal": Deal(r), "after_deal": AfterDeal(r), "peek": Peek(r),
                       "naturals": Naturals(r), "play": Play(r), "check_hand": CheckHand(r),
                       "next_hand": NextHand(r), "dealer": DealerReveals(r),
                       "dealer_draws": DealerDraws(r), "settle": Settle(r)}

    def end_hand(self, s, ctx) -> None:
        """Table cards to the discard tray; reshuffle if the cut card was reached."""
        for zone in ("up", "hole", "dealer") + tuple(f"hand{h}" for h in range(self.rules.max_hands)):
            for card in s.cards(zone):
                ctx.move(card, to="discard")
        pen = self.rules.penetration
        if pen is not None and ctx.state.count("shoe") <= sum(self.shoe) * (1 - pen):
            for card in ctx.state.cards("discard"):
                ctx.move(card, to="shoe")

    def utility(self, s, player: int) -> Fraction:
        """Money won or lost in the hand, in units of the original bet (S8: the
        objective is money; a hand's result does not depend on earlier hands)."""
        return s.net


def situation_of(s) -> tuple[tuple[str, ...], str, int, bool]:
    """What the player sees at a decision: own active hand, dealer up card, number of
    hands, whether aces were split. Used by strategies playing through the engine."""
    return _ranks(s, f"hand{s.active}"), _ranks(s, "up")[0], s.n_hands, s.split_aces
