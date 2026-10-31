"""Per-game presentation for the generic circle layout (docs/architecture/gui.md).

ONE profile class (CircleProfile) does the work for every game: seats around the
table, piles in the middle, the card grid, the focused player or pile, the
focused card, prompts and labels. A game only gives HINTS (gui.md §3, level 2):
its seats and which zones they show, the piles, short zone labels, and optional
hooks (game questions, notes such as a blackjack total, advice on your moves).

Profiles read beliefs only through the common API of joker/probability/views.py
(WorldsBelief / ExchangeableBelief): aggregates over possible worlds, never one
world (non-leakage, S5.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..core import CardRef, Engine, StepKind
from ..core.card import FACE, facet_dict
from ..core.observation import VarSeen
from ..games.blackjack import RANKS as BJ_RANKS, Blackjack, BlackjackRules, hand_value, is_blackjack
from ..games.briscola import POINTS, Briscola2
from ..games.scopone import VALUES, capture_sets, hand_score, make_scopone
from ..live import ExchangeableSession, LiveSession, Pending
from ..strategy.blackjack import BlackjackSolver

SUIT_NAMES = {"coins": "Coins", "cups": "Cups", "swords": "Swords", "clubs": "Clubs",
              "hearts": "Hearts", "diamonds": "Diamonds", "spades": "Spades"}
RANK_NAMES = {"A": "Ace", "J": "Jack", "Q": "Queen", "K": "King", "T": "10"}
ITALIAN_SUITS = ("coins", "cups", "swords", "clubs")
ITALIAN_RANKS = ("A", "2", "3", "4", "5", "6", "7", "J", "Q", "K")


def card_name(face: dict) -> str:
    rank = RANK_NAMES.get(face.get("rank"), face.get("rank"))
    suit = face.get("suit")
    return f"{rank} of {SUIT_NAMES.get(suit, suit)}" if suit else str(rank)


def attrs_card(attrs) -> dict:
    return {"face": facet_dict(attrs, FACE), "back": facet_dict(attrs, "back")}


def type_card(t) -> dict:
    return {"face": t.face, "back": t.back}


def _q(label: str, p: Fraction | float) -> dict:
    return {"label": label, "fraction": str(p) if isinstance(p, Fraction) else f"{p:.6f}",
            "percent": float(p) * 100}


def _find_type(engine: Engine, suit: str | None, rank: str):
    return next(c.type for c in engine.cards if c.face.get("suit") == suit and c.face.get("rank") == rank)


@dataclass(frozen=True)
class Seat:
    """A place at the table. `zones`: the zones shown there (hidden ones give the
    number on the avatar and are what its odds are about). `player`: the engine
    player sitting there, None for a participant that never decides (a dealer)."""

    key: str
    name: str                     # short, on the avatar
    team: str                     # "me" | "ally" | "opp"
    zones: tuple[str, ...]
    player: int | None = None
    called: str | None = None     # in sentences: "your right opponent"


@dataclass(frozen=True)
class Pile:
    """A zone in the middle of the table (no seat): table, stock, shoe..."""

    zone: str
    label: str


class CircleProfile:
    """Generic presentation; subclasses give the hints and the hooks."""

    id = ""
    title = ""
    layout = "circle"
    me = 0
    setup_question = "Who deals?"
    setups: list[dict] = []
    seats: tuple[Seat, ...] = ()       # in order of play, starting from you
    piles: tuple[Pile, ...] = ()
    count_only: frozenset[str] = frozenset()   # zones shown as a number only (taken piles)
    zone_labels: dict[str, str] = {}   # short location labels for the card grid
    zone_prompts: dict[str, str] = {}  # "which card ...?" per destination zone
    suits: tuple[str, ...] = ()        # display order (else deck order)
    ranks: tuple[str, ...] = ()
    my_turn_prompt = "Your turn — what do you play?"
    event_prompt = "What happened?"

    # --- session ---------------------------------------------------------------------

    def new_session(self, setup: int):
        raise NotImplementedError

    def public(self) -> dict:
        return {"id": self.id, "title": self.title, "setups": self.setups, "question": self.setup_question}

    # --- deck and locations ------------------------------------------------------------

    def deck(self, engine: Engine) -> list[dict]:
        """Rows of the card grid / picker: one per suit (one row if cards have no suit)."""
        types = list(dict.fromkeys(c.type for c in engine.cards))
        suits = list(dict.fromkeys(t.face.get("suit") for t in types))
        suits.sort(key=lambda s: self.suits.index(s) if s in self.suits else len(self.suits))
        ranks = list(dict.fromkeys(t.face.get("rank") for t in types))
        ranks.sort(key=lambda r: self.ranks.index(r) if r in self.ranks else len(self.ranks))
        present = {(t.face.get("suit"), t.face.get("rank")) for t in types}
        return [{"suit": s, "ranks": [r for r in ranks if (s, r) in present]} for s in suits]

    def hidden_zones(self, engine: Engine) -> set[str]:
        """Zones whose faces you do not see and whose cards are not recorded piles."""
        return {z.name for z in engine.zones.values()
                if FACE not in z.visible_facets(self.me, engine.all_facets) and z.name not in self.count_only}

    def seat_of_player(self, player) -> Seat | None:
        return next((s for s in self.seats if s.player == player), None)

    def zone_kind(self, zone: str) -> str:
        if zone in self.count_only:
            return "taken"
        seat = next((s for s in self.seats if zone in s.zones), None)
        return seat.team if seat else "table"

    # --- prompts and labels ------------------------------------------------------------

    def choice_json(self, choice) -> dict:
        """card: the card seen moving (if any). action: the option's name when the
        option is not "play this card" (no card among its arguments: stand, hit,
        split...) — then the page shows buttons instead of the card picker."""
        card = next((attrs_card(m.attrs) for m in choice.moves if facet_dict(m.attrs, FACE)), None)
        own = choice.own
        plays_card = own is not None and any(isinstance(a, CardRef) for a in own.args)
        action = own.kind if own is not None and not plays_card else None
        return {"card": card, "action": action, "dst": choice.moves[0].dst if choice.moves else None}

    def describe(self, choice: dict) -> str:
        """Button text for a choice that is not just a card."""
        if choice.get("action"):
            return choice["action"].capitalize()
        if choice.get("card"):
            return card_name(choice["card"]["face"])
        return "Nothing else"

    def prompt(self, pending: Pending) -> tuple[str, str]:
        """(question, who): who = me / ally / opp / nature, for the colors."""
        if pending.kind is StepKind.CHOICE:
            seat = self.seat_of_player(pending.actors[0])
            if seat is None or seat.team == "me":
                return self.my_turn_prompt, "me"
            return f"What did {seat.called or seat.name} play?", seat.team
        choices = [self.choice_json(c) for c in pending.choices]
        if all(c["card"] for c in choices):
            dst = choices[0]["dst"]
            if dst in self.zone_prompts:
                return self.zone_prompts[dst], self.zone_kind(dst)
            if self.zone_kind(dst) == "me":
                return "Which card did you get?", "me"
            return f"Which card went to {self.zone_labels.get(dst, dst)}?", "nature"
        return self.event_prompt, "nature"

    def label(self, pending: Pending, who: str, choice: dict) -> str:
        """History line for a choice the person made."""
        name = card_name(choice["card"]["face"]) if choice.get("card") else None
        if pending.kind is StepKind.CHOICE:
            seat = self.seat_of_player(pending.actors[0])
            actor = "You" if seat is None or seat.team == "me" else seat.name
            return f"{actor} played the {name}" if name and not choice.get("action") else f"{actor}: {self.describe(choice)}"
        if name and choice.get("dst"):
            return f"{self.zone_labels.get(choice['dst'], choice['dst'])}: {name}"
        return self.describe(choice)

    # --- hooks (override per game) -------------------------------------------------------

    def band(self, engine, belief) -> tuple[str, str]:
        return "Them", "Us"

    def dealer_seat(self, belief) -> str | None:
        return None

    def highlight_suit(self, belief) -> str | None:
        """A suit to highlight on every card (e.g. the trump suit)."""
        return None

    def zone_note(self, engine, belief, zone: str) -> str | None:
        return None

    def questions(self, engine, belief, target: dict) -> list[dict]:
        return []

    def advice(self, engine, belief, pending: Pending, choices: list[dict]) -> dict[int, float] | None:
        """Expected value of each of your options (strategy, Goal 2), or None."""
        return None

    def final(self, engine, belief) -> dict | None:
        """{"summary": str, "headers": [...], "rows": [[...], ...]} when the hand is over."""
        return None

    def unseen_on_table(self, engine, belief, seat: Seat, pending) -> int:
        """Face-down cards physically at a seat that the engine has not drawn yet
        (lazy draws, DR-2). Default: none."""
        return 0

    # --- the table ------------------------------------------------------------------------

    def targets(self, engine, belief, pending) -> list[dict]:
        """What the odds can be about: seats and piles holding cards you cannot see."""
        hidden = self.hidden_zones(engine)
        out = []
        for seat in self.seats:
            zones = [z for z in seat.zones if z in hidden and belief.zone_count(z)]
            if seat.team != "me" and zones:
                out.append({"key": seat.key, "name": seat.called or seat.name, "short": seat.name,
                            "team": seat.team, "zones": zones, "reading": "holds"})
        for pile in self.piles:
            if pile.zone in hidden and belief.zone_count(pile.zone):
                out.append({"key": pile.zone, "name": pile.label, "short": pile.label, "team": "pile",
                            "zones": [pile.zone], "reading": "next"})
        return out

    def default_target(self, targets: list[dict], pending: Pending | None) -> dict | None:
        """The player to act; on your turn (or a deal) the next seat; else the first."""
        if not targets:
            return None
        by_key = {t["key"]: t for t in targets}
        if pending is not None and pending.kind is StepKind.CHOICE:
            seat = self.seat_of_player(pending.actors[0])
            if seat is not None and seat.key in by_key:
                return by_key[seat.key]
        for seat in self.seats[1:]:
            if seat.key in by_key:
                return by_key[seat.key]
        return targets[0]

    def _p_card(self, belief, zones: list[str], t, copies: int, reading: str) -> Fraction:
        if reading == "next":
            n = sum(belief.zone_count(z) for z in zones)
            return sum((belief.expected(z, t) for z in zones), Fraction(0)) / n if n else Fraction(0)
        if copies == 1:
            return sum((belief.expected(z, t) for z in zones), Fraction(0))
        return belief.prob_at_least(zones[0], 1, lambda x: x == t)

    def table_view(self, engine: Engine, belief, view: dict, pending: Pending | None) -> dict:
        hidden = self.hidden_zones(engine)
        targets = self.targets(engine, belief, pending)
        auto = self.default_target(targets, pending)
        target = next((t for t in targets if t["key"] == view.get("focus")), None) or auto
        card = self._card_from_view(engine, view.get("card"))
        actors = pending.actors if pending is not None and pending.kind is StepKind.CHOICE else ()
        dealer = self.dealer_seat(belief)

        def zone_json(z: str) -> dict:
            known = [type_card(t) for t in belief.known_cards(z)] if z not in self.count_only else []
            return {"zone": z, "label": self.zone_labels.get(z, z), "count": belief.zone_count(z),
                    "known": known, "show": "count" if z in self.count_only else "cards",
                    "note": self.zone_note(engine, belief, z)}

        seats = []
        for seat in self.seats:
            row = {"key": seat.key, "name": seat.name, "team": seat.team,
                   "hidden": sum(belief.zone_count(z) - len(belief.known_cards(z))
                                 for z in seat.zones if z in hidden)
                   + self.unseen_on_table(engine, belief, seat, pending),
                   "zones": [zone_json(z) for z in seat.zones],
                   "turn": seat.player is not None and seat.player in actors,
                   "dealer": dealer == seat.key,
                   "target": any(t["key"] == seat.key for t in targets)}
            if card is not None:
                p = self._hold(engine, belief, seat, card, targets)
                row["hold"] = {"percent": float(p) * 100, "fraction": str(p)}
            seats.append(row)

        out = {
            "seats": seats,
            "piles": [{**zone_json(p.zone), "label": p.label,
                       "show": "count" if p.zone in hidden else "cards",
                       "target": any(t["key"] == p.zone for t in targets)} for p in self.piles],
            "band": self.band(engine, belief),
            "highlight_suit": self.highlight_suit(belief),
            "targets": [{k: t[k] for k in ("key", "name", "short", "team")} for t in targets],
            "focus": self._focus(engine, belief, target, target is auto and view.get("focus") is None)
            if target else None,
            "final": self.final(engine, belief) if pending is None else None,
        }
        if card is not None:
            where = self._where(engine, belief, card)
            out["card"] = {**type_card(card), "where": where}
        return out

    def _copies(self, engine, t) -> int:
        return sum(1 for c in engine.cards if c.type == t)

    def _hold(self, engine, belief, seat: Seat, t, targets) -> Fraction:
        """P(the seat has at least one copy of `t`), seen or not."""
        zones = [z for z in seat.zones if z not in self.count_only]
        if any(belief.certain(z, t) for z in zones):
            return Fraction(1)
        target = next((x for x in targets if x["key"] == seat.key), None)
        if target is None:
            return Fraction(0)
        return self._p_card(belief, target["zones"], t, self._copies(engine, t), target["reading"])

    def _where(self, engine, belief, t) -> str | None:
        """Short label of where a single-copy card certainly is (None: not known)."""
        if self._copies(engine, t) != 1:
            return None
        zone = next((z for z in engine.zones if belief.certain(z, t) == 1), None)
        return None if zone is None else self.zone_labels.get(zone, zone)

    def _card_from_view(self, engine, key):
        if not key or "/" not in str(key):
            return None
        suit, rank = str(key).split("/", 1)
        suit = suit or None
        if not any(c.face.get("suit") == suit and c.face.get("rank") == rank for c in engine.cards):
            return None
        return _find_type(engine, suit, rank)

    def _focus(self, engine, belief, target: dict, auto: bool) -> dict:
        zones, reading = target["zones"], target["reading"]
        hidden = self.hidden_zones(engine)
        rows = []
        for row in self.deck(engine):
            cells = []
            for rank in row["ranks"]:
                t = _find_type(engine, row["suit"], rank)
                copies = self._copies(engine, t)
                seen = copies - sum(belief.expected(z, t) for z in hidden)
                unseen = copies - int(seen)
                where = self._where(engine, belief, t)
                p = self._p_card(belief, zones, t, copies, reading)
                cells.append({"rank": rank, "copies": copies, "unseen": unseen,
                              "status": where, "kind": self._kind_of_where(engine, belief, t) if where else None,
                              "p": float(p) * 100, "fraction": str(p)})
            rows.append({"suit": row["suit"], "cells": cells})
        by_rank = []
        if len(rows) > 1:                                  # suited deck: a per-rank summary
            for rank in dict.fromkeys(r for row in self.deck(engine) for r in row["ranks"]):
                match = lambda t, r=rank: t.face.get("rank") == r
                unseen = sum(c["unseen"] for row in rows for c in row["cells"] if c["rank"] == rank)
                if reading == "next":
                    n = sum(belief.zone_count(z) for z in zones)
                    p = sum((belief.expected_matching(z, match) for z in zones), Fraction(0)) / n if n else Fraction(0)
                else:
                    p = belief.prob_at_least(zones[0], 1, match)
                by_rank.append({"rank": rank, "unseen": unseen, "percent": float(p) * 100,
                                "expected": float(sum((belief.expected_matching(z, match) for z in zones), Fraction(0)))})
        return {"key": target["key"], "name": target["name"], "team": target["team"], "auto": auto,
                "reading": reading, "count": sum(belief.zone_count(z) for z in zones),
                "questions": self.questions(engine, belief, target), "cards": rows, "ranks": by_rank,
                "worlds": f"{belief.support:,}"}

    def _kind_of_where(self, engine, belief, t) -> str:
        zone = next(z for z in engine.zones if belief.certain(z, t) == 1)
        return self.zone_kind(zone)


# --- Scopone ---------------------------------------------------------------------------------

class ScoponeProfile(CircleProfile):
    """Scopone scientifico seen by player 0. Play goes to the right: 1 is the next
    player (right opponent), 2 the partner, 3 the left opponent. Exact combinatorial
    method (exchangeable unseen cards)."""

    id = "scopone"
    title = "Scopone scientifico"
    setups = [{"label": "I deal", "value": 0, "color": "blue"},
              {"label": "Right deals", "value": 1, "color": "red"},
              {"label": "Partner deals", "value": 2, "color": "blue"},
              {"label": "Left deals", "value": 3, "color": "red"}]
    seats = (Seat("p0", "You", "me", ("hand0",), 0),
             Seat("p1", "Right", "opp", ("hand1",), 1, "your right opponent"),
             Seat("p2", "Partner", "ally", ("hand2",), 2, "your partner"),
             Seat("p3", "Left", "opp", ("hand3",), 3, "your left opponent"))
    piles = (Pile("table", "Table"),)
    count_only = frozenset({"taken0", "taken1"})
    zone_labels = {"hand0": "You", "hand1": "Right", "hand2": "Partner", "hand3": "Left",
                   "table": "Table", "taken0": "Us", "taken1": "Them"}
    suits = ITALIAN_SUITS
    ranks = ITALIAN_RANKS

    def new_session(self, setup: int):
        return ExchangeableSession(Engine(make_scopone()), self.me, {"dealer": setup})

    def choice_json(self, choice) -> dict:
        played, captures = None, []
        for move in choice.moves:
            card = attrs_card(move.attrs)
            if move.src.startswith("hand") and move.dst == "table":
                played = card
            elif move.src == "table" and move.dst.startswith("taken") and card != played:
                captures.append(card)
        if played is None:                       # a draw: the card shown is the one drawn
            played = next((attrs_card(m.attrs) for m in choice.moves), None)
        scopa = any(isinstance(p, VarSeen) and p.name.startswith("scope")
                    for p in choice.observation.perceived)
        return {"card": played, "action": None, "dst": choice.moves[0].dst if choice.moves else None,
                "captures": captures, "scopa": scopa}

    def label(self, pending: Pending, who: str, choice: dict) -> str:
        name = card_name(choice["card"]["face"]) if choice.get("card") else "?"
        if pending.kind is not StepKind.CHOICE:
            return f"You got the {name}"
        seat = self.seat_of_player(pending.actors[0])
        actor = "You" if seat.team == "me" else seat.called.removeprefix("your ").capitalize()
        text = f"{actor} played the {name}"
        if choice["captures"]:
            text += ", taking " + " + ".join(card_name(c["face"]) for c in choice["captures"])
        if choice["scopa"]:
            text += " — SCOPA!"
        return text

    def band(self, engine, belief):
        return (f"Them · {belief.public_var('scope1')} scope · {belief.zone_count('taken1')} cards",
                f"Us · {belief.public_var('scope0')} scope · {belief.zone_count('taken0')} cards")

    def dealer_seat(self, belief):
        d = belief.public_var("dealer")
        return f"p{d}" if d is not None else None

    def final(self, engine, belief):
        taken = {t: [x.face for x in belief.known_cards(f"taken{t}")] for t in (0, 1)}
        f = hand_score(taken, {0: belief.public_var("scope0"), 1: belief.public_var("scope1")})
        rows = [[label, f[0][k], f[1][k]] for k, label in
                (("cards", "Cards"), ("coins", "Coins"), ("settebello", "Settebello"),
                 ("primiera", "Primiera"), ("scope", "Scope"), ("total", "Total"))]
        return {"summary": "Hand over", "headers": ["", "Us", "Them"], "rows": rows}

    def questions(self, engine, belief, target):
        zone = target["zones"][0]
        if target["reading"] != "holds":
            return []
        out = []
        table = belief.known_cards("table")
        sweep = {r for r in self.ranks if table and any(len(s) == len(table)
                                                        for s in capture_sets(VALUES[r], table))}
        take = {r for r in self.ranks if capture_sets(VALUES[r], table)}
        if sweep:
            out.append(_q("Can sweep the table now (scopa)",
                          belief.prob_at_least(zone, 1, lambda t: t.face["rank"] in sweep)))
        if take:
            out.append(_q("Can take something from the table",
                          belief.prob_at_least(zone, 1, lambda t: t.face["rank"] in take)))
        settebello = _find_type(engine, "coins", "7")
        if self._where(engine, belief, settebello) is None:
            out.append(_q("Holds the settebello (7♦)", belief.expected(zone, settebello)))
        sevens = lambda t: t.face["rank"] == "7"
        if belief.expected_matching(zone, sevens):
            out.append(_q("Holds at least one 7", belief.prob_at_least(zone, 1, sevens)))
        return out


# --- Briscola ----------------------------------------------------------------------------------

class BriscolaProfile(CircleProfile):
    """Two-player Briscola seen by player 0. Exact enumeration of worlds."""

    id = "briscola"
    title = "Briscola"
    setups = [{"label": "I deal", "value": 0, "color": "blue"},
              {"label": "Opponent deals", "value": 1, "color": "red"}]
    seats = (Seat("p0", "You", "me", ("hand0", "won0"), 0),
             Seat("p1", "Opponent", "opp", ("hand1", "won1"), 1, "your opponent"))
    piles = (Pile("table", "Table"), Pile("trump_card", "Trump card"), Pile("stock", "Stock"))
    count_only = frozenset({"won0", "won1"})
    zone_labels = {"hand0": "You", "hand1": "Opp", "table": "Table", "trump_card": "Trump",
                   "won0": "Taken", "won1": "Taken", "stock": "the stock"}
    zone_prompts = {"trump_card": "Which card was turned up as trump?"}
    suits = ITALIAN_SUITS
    ranks = ITALIAN_RANKS

    def new_session(self, setup: int):
        return LiveSession(Engine(Briscola2()), self.me, {"dealer": setup})

    def band(self, engine, belief):
        def points(zone):
            return sum(POINTS.get(t.face["rank"], 0) for t in belief.known_cards(zone))
        trump = belief.public_var("trump_suit")
        suffix = f" · trump {SUIT_NAMES[trump]}" if trump else ""
        return f"Opponent · {points('won1')} pts", f"You · {points('won0')} pts{suffix}"

    def dealer_seat(self, belief):
        d = belief.public_var("dealer")
        return f"p{d}" if d is not None else None

    def highlight_suit(self, belief):
        return belief.public_var("trump_suit")

    def final(self, engine, belief):
        pts = [sum(POINTS.get(t.face["rank"], 0) for t in belief.known_cards(f"won{p}")) for p in (0, 1)]
        verdict = "You win" if pts[0] > 60 else "Opponent wins" if pts[1] > 60 else "Draw (60–60)"
        return {"summary": verdict, "headers": ["", "You", "Opponent"], "rows": [["Points", pts[0], pts[1]]]}

    def questions(self, engine, belief, target):
        trump = belief.public_var("trump_suit")
        if trump is None:
            return []
        name = SUIT_NAMES[trump]
        zone = target["zones"][0]
        is_trump = lambda t: t.face["suit"] == trump
        if target["reading"] == "next":
            return [_q(f"The next card is a {name}", belief.expected_matching(zone, is_trump) / belief.zone_count(zone))]
        out = []
        for rank, label in (("A", "Ace"), ("3", "3")):            # only while still unaccounted for
            card = _find_type(engine, trump, rank)
            if self._where(engine, belief, card) is None:
                out.append(_q(f"Holds the trump {label}", belief.expected(zone, card)))
        return out + [_q(f"Holds at least one {name}", belief.prob_at_least(zone, 1, is_trump))]


# --- Blackjack ---------------------------------------------------------------------------------

class BlackjackProfile(CircleProfile):
    """Blackjack, you against the dealer (ROADMAP rung 1). Exact enumeration of
    worlds (few: only the dealer's hole card is ever hidden). Advice on your moves
    from the exact blackjack solver (strategy, Goal 2)."""

    id = "blackjack"
    title = "Blackjack"
    setup_question = "Dealer stands on soft 17 · double on any two · double after split · split once · blackjack pays 3:2. How many decks?"
    setups = [{"label": "6 decks", "value": 6, "color": "blue"},
              {"label": "1 deck", "value": 1, "color": "red"}]
    rules_for = staticmethod(lambda decks: BlackjackRules(decks=decks, max_hands=2))
    seats = (Seat("you", "You", "me", ("hand0", "hand1"), 0),
             Seat("dealer", "Dealer", "opp", ("up", "hole", "dealer"), None, "the dealer"))
    piles = (Pile("shoe", "Shoe"),)
    zone_labels = {"hand0": "Your hand", "hand1": "Your second hand", "up": "Up card",
                   "hole": "Hole card", "dealer": "Dealer's cards", "shoe": "Shoe"}
    zone_prompts = {"up": "Which card is the dealer showing?",
                    "dealer": "Which card did the dealer turn over or draw?"}
    ranks = BJ_RANKS
    my_turn_prompt = "Your move — what do you do?"
    event_prompt = "Did the dealer peek a blackjack?"

    def __init__(self) -> None:
        self._solvers: dict = {}

    def new_session(self, setup: int):
        return LiveSession(Engine(Blackjack(self.rules_for(setup))), self.me)

    # The engine draws the hole card only when needed (lazy draw, DR-2): unless the
    # dealer must peek, it is still in the shoe. At the table it is face down in
    # front of the dealer, and — never seen — it is exactly as likely as the next
    # card of the shoe. So the dealer's seat shows it, and its odds are the shoe's.
    def _virtual_hole(self, belief, pending) -> bool:
        return (pending is not None and belief.zone_count("up") == 1
                and not belief.zone_count("hole") and not belief.zone_count("dealer"))

    def unseen_on_table(self, engine, belief, seat, pending):
        return int(seat.key == "dealer" and self._virtual_hole(belief, pending))

    def targets(self, engine, belief, pending):
        out = super().targets(engine, belief, pending)
        if self._virtual_hole(belief, pending):
            out.insert(0, {"key": "dealer", "name": "the dealer's hole card", "short": "Dealer",
                           "team": "opp", "zones": ["shoe"], "reading": "next"})
        else:
            for t in out:
                if t["key"] == "dealer":
                    t["name"] = "the dealer's hole card"
        return out

    def describe(self, choice):
        if choice.get("action"):
            return {"stand": "Stand", "hit": "Hit", "double": "Double", "split": "Split"}.get(
                choice["action"], choice["action"].capitalize())
        if choice.get("card"):
            name = card_name(choice["card"]["face"])
            return f"Blackjack (hole card {name})" if choice.get("dst") == "dealer" else name
        return "No blackjack"

    # cards seen and unseen, as the solver wants them: counts per rank A..T
    def _ranks(self, belief, zone):
        return tuple(sorted(BJ_RANKS.index(t.face["rank"]) for t in belief.known_cards(zone)))

    def _unseen(self, engine, belief) -> tuple[int, ...]:
        counts = [0] * 10
        for c in engine.cards:
            counts[BJ_RANKS.index(c.face["rank"])] += 1
        for zone in ("up", "dealer", "hand0", "hand1"):
            for i in self._ranks(belief, zone):
                counts[i] -= 1
        return tuple(counts)

    def _solver(self, engine):
        rules = engine.game.rules
        if rules not in self._solvers:
            self._solvers = {rules: BlackjackSolver(rules)}
        return self._solvers[rules]

    def zone_note(self, engine, belief, zone):
        if zone.startswith("hand"):
            ranks = [t.face["rank"] for t in belief.known_cards(zone)]
            if not ranks:
                return None
            bets = belief.public_var("bets")
            n_hands = belief.public_var("n_hands")
            doubled = " · doubled" if bets and bets[int(zone[4:])] == 2 else ""
            playing = "▶ " if n_hands > 1 and belief.public_var("active") == int(zone[4:]) else ""
            return playing + _total_text(ranks, natural=n_hands == 1) + doubled
        if zone == "dealer" and belief.zone_count("dealer"):
            ranks = [t.face["rank"] for z in ("up", "dealer") for t in belief.known_cards(z)]
            return _total_text(ranks)
        return None

    def band(self, engine, belief):
        r = engine.game.rules
        bets = belief.public_var("bets") or (1,)
        decks = f"{r.decks} deck{'s' * (r.decks > 1)}"
        return (f"Dealer · {decks} · {'H17' if r.hit_soft_17 else 'S17'}",
                f"You · bet {sum(bets)}")

    def dealer_seat(self, belief):
        return "dealer"

    def final(self, engine, belief):
        net = belief.public_var("net")
        if net is None:
            return None
        if net == 0:
            return {"summary": "Push: your bet comes back", "headers": [], "rows": []}
        verdict = "You win" if net > 0 else "You lose"
        return {"summary": f"{verdict}: {float(net):+g} bet{'s' * (abs(net) != 1)}", "headers": [], "rows": []}

    def questions(self, engine, belief, target):
        up = self._ranks(belief, "up")
        if not up:
            return []
        deck = self._unseen(engine, belief)
        solver = self._solver(engine)
        if target["key"] == "dealer":
            dealer = self._ranks(belief, "dealer")
            if dealer:                                   # the dealer is drawing: from its cards
                cards = up + dealer
                hard = sum(c + 1 for c in cards)
                dist = solver._dealer_rest(deck, hard, 0 in cards)
            else:
                dist = solver.dealer(deck, up[0])
            out = [_q("Dealer busts", dist[5])]
            out += [_q(f"Dealer ends on {t}", p) for t, p in zip((17, 18, 19, 20, 21), dist[:5]) if p > 0]
            return out
        dealer = self._ranks(belief, "dealer")
        if target["reading"] == "next" and dealer:      # the dealer is drawing
            cards = up + dealer
            dist = solver._dealer_rest(deck, sum(c + 1 for c in cards), 0 in cards)
            return [_q("Dealer busts", dist[5])]
        if target["reading"] == "next":
            active = belief.public_var("active") or 0
            ranks = [t.face["rank"] for t in belief.known_cards(f"hand{active}")]
            n = sum(deck)
            out = []
            if ranks and hand_value(ranks)[0] < 21:
                bust = sum(k for i, k in enumerate(deck) if hand_value(ranks + [BJ_RANKS[i]])[0] > 21)
                out.append(_q("The next card busts your hand", Fraction(bust, n)))
            out.append(_q("The next card is a 10", Fraction(deck[9], n)))
            return out
        return []

    def advice(self, engine, belief, pending, choices):
        if pending.kind is not StepKind.CHOICE or pending.actors != (self.me,):
            return None
        active = belief.public_var("active")
        cards = self._ranks(belief, f"hand{active}")
        up = self._ranks(belief, "up")
        if not up or not cards:
            return None
        deck = self._unseen(engine, belief)
        solver = self._solver(engine)
        out = {}
        for c in choices:
            try:
                out[c["index"]] = solver._q(deck, up[0], cards, belief.public_var("n_hands"),
                                            belief.public_var("split_aces"), c["action"])
            except NotImplementedError:
                pass
        return out


def _total_text(ranks: list[str], natural: bool = True) -> str:
    total, soft = hand_value(ranks)
    if total > 21:
        return f"{total} · bust"
    if natural and is_blackjack(ranks):
        return "Blackjack"
    return f"{'soft ' if soft else ''}{total}"


PROFILES = {"scopone": ScoponeProfile(), "briscola": BriscolaProfile(), "blackjack": BlackjackProfile()}
