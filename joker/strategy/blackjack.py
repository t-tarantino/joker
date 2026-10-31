"""Fast exact blackjack analysis (ROADMAP rung 1).

Game-specific and fast (floating point), checked against the generic exact solver
(`expectimax.SoloExpectimax`, Fractions, through the engine) and against published
tables. Same rules as `joker.games.blackjack`, which this module imports.

The shoe is a tuple of 10 counts (A, 2, ..., 9, T), or None for an infinite deck
(every draw: 1/13 per rank, 4/13 for T).

Every per-hand value is conditional on the dealer NOT having blackjack (the dealer
has already peeked), like published tables. Peeking is information: when the up
card is an A (or a T), the hole card is known not to be a T (an A). Exact
consequence (Griffin, "The Theory of Blackjack"): with n unseen cards, n_k of them
the blackjack-completing rank k,
    P(next card = k)      = n_k / (n - 1)
    P(next card = i != k) = n_i / (n - 1) * (n - n_k - 1) / (n - n_k)
and the dealer's hole card is drawn from the non-k cards only.

Splitting:
- infinite deck: exact, any number of hands (resplits), since hands are then
  independent;
- finite deck, split once (max_hands = 2): Griffin's approximation, each split
  hand computed with both pair cards removed (error ~3e-6 per value, Nairn 2019);
- finite deck with resplits: not implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from ..core import Option
from ..games.blackjack import (RANKS, BlackjackRules, legal_actions, shoe_counts,
                               situation_of)

ACE, TEN = 0, 9
VALUES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
INFINITE = tuple(4 / 13 if i == TEN else 1 / 13 for i in range(10))
UPCARDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)        # chart order: 2..9, T, A
DEALER_TOTALS = (17, 18, 19, 20, 21)            # outcome vector: these, then bust


@dataclass(frozen=True)
class Situation:
    """What the player knows at a decision (as used by basic strategy)."""

    cards: tuple[str, ...]      # the hand being played, sorted ranks
    up: str                     # dealer up card
    options: tuple[str, ...]    # legal actions
    n_hands: int                # hands so far (> 1 after a split)
    split_aces: bool


Policy = Callable[[Situation], str]


def _total(cards: tuple[int, ...]) -> tuple[int, bool]:
    hard = sum(VALUES[c] for c in cards)
    if ACE in cards and hard + 10 <= 21:
        return hard + 10, True
    return hard, False


def _add(cards: tuple[int, ...], c: int) -> tuple[int, ...]:
    return tuple(sorted(cards + (c,)))


def _remove(deck, c: int):
    if deck is None or not deck[c]:      # drawn after the shoe ran dry: see _dry
        return None
    return deck[:c] + (deck[c] - 1,) + deck[c + 1:]


def _dry(deck, k: int | None = None) -> bool:
    """No card left to draw (beside a hole card known not to be k). At the table the
    discards are reshuffled; these rare paths are valued as a fresh shoe (deck None,
    standard proportions): an approximation, only for nearly empty shoes."""
    if deck is None:
        return False
    n = sum(deck)
    return n == 0 if k is None else n <= 1 or n - deck[k] <= 0


def _bj_rank(up: int) -> int | None:
    """The hole card that would give the dealer blackjack."""
    return TEN if up == ACE else ACE if up == TEN else None


class BlackjackSolver:
    """Exact expected values for one rule set.

    policy=None: optimal play, decided on the exact cards seen (composition
    dependent). With a policy: the values of playing that policy. split_choice
    ="best" lets the solver decide splits by value whatever the policy says (how
    Nairn 2019 evaluates its basic strategy). always_resplit=True values a split as
    "resplit whenever allowed" (the convention of published split tables; it only
    changes splits that are bad plays anyway).

    proportions: an "infinite deck" with these probabilities per rank A..T instead
    of the standard 1/13 (4/13 for T): every card is drawn with the same odds, no
    card removal within the hand. Used for a fast estimate on a partly dealt shoe."""

    def __init__(self, rules: BlackjackRules, policy: Policy | None = None,
                 shoe: tuple[int, ...] | None = None, split_choice: str = "policy",
                 always_resplit: bool = False,
                 proportions: tuple[float, ...] | None = None) -> None:
        self.rules = rules
        self.policy = policy
        self.split_choice = split_choice
        self.always_resplit = always_resplit
        if proportions is not None:
            if shoe is not None:
                raise ValueError("give either a shoe or proportions")
        elif shoe is None and rules.decks is not None:
            shoe = shoe_counts(rules.decks)
        self.shoe = shoe                                    # None = infinite deck
        self._inf = INFINITE if proportions is None else tuple(proportions)
        self._draws: dict = {}
        self._dealer_cache: dict = {}
        self._rest_cache: dict = {}
        self._values: dict = {}
        self._initial: dict = {}

    # --- probabilities -------------------------------------------------------------------

    def draw_probs(self, deck, up: int) -> tuple[float, ...]:
        """Next player card, given the unseen cards (hole card included) and the
        dealer not having blackjack."""
        if deck is None:
            return self._inf
        if _dry(deck, _bj_rank(up)):
            return INFINITE
        key = (deck, up)
        cached = self._draws.get(key)
        if cached is None:
            n = sum(deck)
            k = _bj_rank(up)
            if k is None:
                cached = tuple(c / n for c in deck)
            else:
                nk = deck[k]
                cached = tuple(nk / (n - 1) if i == k else deck[i] / (n - 1) * (n - nk - 1) / (n - nk)
                               for i in range(10))
            self._draws[key] = cached
        return cached

    def dealer(self, deck, up: int) -> tuple[float, ...]:
        """Probabilities of the dealer's final 17, 18, 19, 20, 21, bust, given the
        unseen cards (hole included) and no dealer blackjack."""
        key = (deck, up)
        cached = self._dealer_cache.get(key)
        if cached is not None:
            return cached
        k = _bj_rank(up)
        if _dry(deck, k):
            deck = None
        if deck is None:
            hole = [p / (1 - self._inf[k]) if i != k else 0.0 for i, p in enumerate(self._inf)] \
                if k is not None else list(self._inf)
        else:
            n = sum(deck) - (deck[k] if k is not None else 0)
            hole = [0.0 if i == k else deck[i] / n for i in range(10)]
        out = [0.0] * 6
        for i, p in enumerate(hole):
            if p:
                sub = self._dealer_rest(_remove(deck, i), VALUES[up] + VALUES[i], up == ACE or i == ACE)
                for j in range(6):
                    out[j] += p * sub[j]
        result = tuple(out)
        self._dealer_cache[key] = result
        return result

    def _dealer_rest(self, deck, hard: int, ace: bool) -> tuple[float, ...]:
        key = (deck, hard, ace)
        cached = self._rest_cache.get(key)
        if cached is not None:
            return cached
        soft = ace and hard + 10 <= 21
        total = hard + 10 if soft else hard
        if total > 21:
            result = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        elif total > 17 or (total == 17 and not (soft and self.rules.hit_soft_17)):
            result = tuple(1.0 if t == total else 0.0 for t in DEALER_TOTALS) + (0.0,)
        else:
            out = [0.0] * 6
            if _dry(deck):
                deck = None
            n = None if deck is None else sum(deck)
            for i in range(10):
                p = self._inf[i] if deck is None else deck[i] / n
                if p:
                    sub = self._dealer_rest(_remove(deck, i), hard + VALUES[i], ace or i == ACE)
                    for j in range(6):
                        out[j] += p * sub[j]
            result = tuple(out)
        self._rest_cache[key] = result
        return result

    # --- values of actions ---------------------------------------------------------------

    def stand_value(self, deck, up: int, total: int) -> float:
        if total > 21:
            return -1.0
        d = self.dealer(deck, up)
        ev = d[5]
        for j, t in enumerate(DEALER_TOTALS):
            ev += d[j] if total > t else -d[j] if total < t else 0.0
        return ev

    def _q(self, deck, up: int, cards, n_hands: int, split_aces: bool, action: str) -> float:
        if action == "stand":
            return self.stand_value(deck, up, _total(cards)[0])
        probs = self.draw_probs(deck, up)
        if action == "double":
            return 2 * sum(p * self.stand_value(_remove(deck, i), up, _total(_add(cards, i))[0])
                           for i, p in enumerate(probs) if p)
        if action == "hit":
            return sum(p * self._value(_remove(deck, i), up, _add(cards, i), n_hands, split_aces)
                       for i, p in enumerate(probs) if p)
        if action == "split":
            return self._split(deck, up, cards[0], n_hands)
        raise ValueError(action)

    def _actions(self, cards, n_hands: int, split_aces: bool) -> tuple[str, ...]:
        return legal_actions(self.rules, tuple(RANKS[c] for c in cards), n_hands, split_aces)

    def _choose(self, deck, up, cards, n_hands, split_aces, actions) -> tuple[str, float]:
        """The action played and its value."""
        if self.policy is None:
            values = {a: self._q(deck, up, cards, n_hands, split_aces, a) for a in actions}
            best = max(values, key=values.get)
            return best, values[best]
        situation = Situation(tuple(RANKS[c] for c in cards), RANKS[up], actions, n_hands, split_aces)
        chosen = self.policy(situation)
        if chosen not in actions:
            raise ValueError(f"policy chose {chosen!r}, not in {actions}")
        value = self._q(deck, up, cards, n_hands, split_aces, chosen)
        if self.split_choice == "best" and "split" in actions and chosen != "split":
            split = self._q(deck, up, cards, n_hands, split_aces, "split")
            if split > value:
                return "split", split
        return chosen, value

    def _value(self, deck, up: int, cards, n_hands: int, split_aces: bool) -> float:
        """Value of a hand that is not a natural, from now on, without splitting it
        (splits are valued by `_split`)."""
        total, soft = _total(cards)
        if total > 21:
            return -1.0
        actions = tuple(a for a in self._actions(cards, n_hands, split_aces) if a != "split")
        if len(actions) <= 1:
            return self.stand_value(deck, up, total)
        if self.policy is None and deck is None:
            key = (None, up, total, soft, len(cards) == 2, n_hands, split_aces)
        else:
            key = (deck, up, cards, n_hands, split_aces)
        cached = self._values.get(key)
        if cached is None:
            cached = self._choose(deck, up, cards, n_hands, split_aces, actions)[1]
            self._values[key] = cached
        return cached

    # --- splitting -----------------------------------------------------------------------

    def _split(self, deck, up: int, s: int, n_hands: int) -> float:
        """Value of splitting a pair of rank s (both cards already out of `deck`),
        summed over all the resulting hands, in units of one original bet."""
        aces = s == ACE
        if deck is None:
            return self._split_infinite(up, s, aces)
        if n_hands != 1 or self.rules.max_hands > 2:
            raise NotImplementedError("finite-deck resplitting is not implemented yet")
        probs = self.draw_probs(deck, up)
        return 2 * sum(p * self._value(_remove(deck, i), up, _add((s,), i), 2, aces)
                       for i, p in enumerate(probs) if p)

    def _split_infinite(self, up: int, s: int, aces: bool) -> float:
        rules = self.rules
        can_resplit = not aces or rules.resplit_aces

        @lru_cache(maxsize=None)
        def pending(n: int, k: int) -> float:
            """Expected total value of k one-card hands still to play, n hands so far."""
            if k == 0:
                return 0.0
            total = 0.0
            for i, p in enumerate(self._inf):
                cards = _add((s,), i)
                keep = self._value(None, up, cards, n, aces) + pending(n, k - 1)
                if i == s and n < rules.max_hands and can_resplit:
                    resplit = pending(n + 1, k + 1)
                    if self.always_resplit:
                        keep = resplit
                    elif self.policy is None or self.split_choice == "best":
                        keep = max(keep, resplit)
                    else:
                        actions = self._actions(cards, n, aces)
                        situation = Situation(tuple(RANKS[c] for c in cards), RANKS[up], actions, n, aces)
                        if self.policy(situation) == "split":
                            keep = resplit
                total += p * keep
            return total

        return pending(2, 2)

    # --- the whole round -------------------------------------------------------------------

    def _unseen(self, cards, up: int):
        deck = self.shoe
        for c in cards + (up,):
            if deck is not None:
                if deck[c] == 0:
                    raise ValueError("card not in the shoe")
            deck = _remove(deck, c)
        return deck

    def action_values(self, c1: str, c2: str, up: str) -> dict[str, float]:
        """Value of each initial action, conditional on no dealer blackjack, then
        playing on optimally (or by the policy). Like the published tables."""
        cards = tuple(sorted((RANKS.index(c1), RANKS.index(c2))))
        u = RANKS.index(up)
        deck = self._unseen(cards, u)
        return {a: self._q(deck, u, cards, 1, False, a) for a in self._actions(cards, 1, False)}

    def initial(self, c1: str, c2: str, up: str) -> tuple[str, float]:
        """(action played, its value) at the first decision, conditional on no dealer
        blackjack. Not for naturals."""
        cards = tuple(sorted((RANKS.index(c1), RANKS.index(c2))))
        u = RANKS.index(up)
        key = (cards, u)
        if key not in self._initial:
            deck = self._unseen(cards, u)
            self._initial[key] = self._choose(deck, u, cards, 1, False, self._actions(cards, 1, False))
        return self._initial[key]

    def round_value(self) -> float:
        """Expected result of a round, per original bet, from a full shoe (the
        negative of the house edge)."""
        payout = float(self.rules.blackjack_pays)
        ev = 0.0
        for c1 in range(10):
            for u in range(10):
                for c2 in range(10):
                    p, deck = self._deal_probability(c1, u, c2)
                    if not p:
                        continue
                    k = _bj_rank(u)
                    if k is None:
                        p_dealer_bj = 0.0
                    elif deck is None:
                        p_dealer_bj = self._inf[k]
                    else:
                        p_dealer_bj = deck[k] / sum(deck)
                    if _total((c1, c2))[0] == 21:
                        value = (1 - p_dealer_bj) * payout
                    else:
                        value = -p_dealer_bj + (1 - p_dealer_bj) * self.initial(RANKS[c1], RANKS[c2], RANKS[u])[1]
                    ev += p * value
        return ev

    def _deal_probability(self, c1: int, u: int, c2: int):
        """P(first player card c1, up card u, second player card c2), unseen deck."""
        if self.shoe is None:
            return self._inf[c1] * self._inf[u] * self._inf[c2], None
        deck, p = self.shoe, 1.0
        for c in (c1, u, c2):
            n = sum(deck)
            if deck[c] == 0:
                return 0.0, None
            p *= deck[c] / n
            deck = _remove(deck, c)
        return p, deck

    # --- basic strategy charts -------------------------------------------------------------

    def chart_code(self, c1: str, c2: str, up: str) -> str:
        """Chart notation for the best first action: H hit, S stand, D double (else
        hit), Ds double (else stand), P split."""
        values = self.action_values(c1, c2, up) if self.policy is None else None
        if values is None:
            action = self.initial(c1, c2, up)[0]
        else:
            action = max(values, key=values.get)
        if action == "split":
            return "P"
        if action == "double":
            return "Ds" if values and values["stand"] > values["hit"] else "D"
        return {"hit": "H", "stand": "S"}[action]


# --- charts -----------------------------------------------------------------------------

CHART_UPS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "A")


def chart_rows() -> dict[str, list[tuple[str, str]]]:
    """Row label -> the two-card hands it covers (hard rows: all non-pair hands)."""
    rows: dict[str, list[tuple[str, str]]] = {}
    for total in range(5, 20):
        rows[f"hard {total}"] = [(a, b) for i, a in enumerate(RANKS[1:], 1) for b in RANKS[i + 1:]
                                 if VALUES[RANKS.index(a)] + VALUES[RANKS.index(b)] == total]
    for r in RANKS[1:9]:
        rows[f"soft A{r}"] = [("A", r)]
    for r in RANKS[1:] + ("A",):
        rows[f"pair {r}{r}"] = [(r, r)]
    return rows


def basic_strategy_chart(solver: BlackjackSolver) -> dict[str, list[str]]:
    """The first-decision chart. With a finite deck the best play can depend on the
    exact two cards: then the cell shows the most common code followed by '*'."""
    chart = {}
    for row, hands in chart_rows().items():
        cells = []
        for up in CHART_UPS:
            codes = [solver.chart_code(a, b, up) for a, b in hands
                     if solver.shoe is None or _possible(solver.shoe, a, b, up)]
            best = max(set(codes), key=codes.count)
            cells.append(best if len(set(codes)) == 1 else best + "*")
        chart[row] = cells
    return chart


def _possible(shoe, *ranks) -> bool:
    need = {r: ranks.count(r) for r in ranks}
    return all(shoe[RANKS.index(r)] >= n for r, n in need.items())


def format_chart(chart: dict[str, list[str]]) -> str:
    lines = ["          " + " ".join(f"{u:>3}" for u in CHART_UPS)]
    for row, cells in chart.items():
        lines.append(f"{row:<10}" + " ".join(f"{c:>3}" for c in cells))
    return "\n".join(lines)


# --- several hands from the same shoe (card counting) -----------------------------------

def unseen_counts(view) -> tuple[int, ...]:
    """In one world: cards per rank A..T the player has not seen, i.e. the shoe
    plus the hole card if it is face down. The solvers' `deck` argument."""
    counts = [0] * 10
    for zone in ("shoe", "hole"):
        for card in view.cards(zone):
            counts[RANKS.index(card.face["rank"])] += 1
    return tuple(counts)


def shoe_mixture(worlds) -> list[tuple[tuple[int, ...], float]]:
    """[(unseen counts, probability), ...] over the possible worlds [(view, weight)].
    Several entries only when cards left the table unseen (e.g. a hole card never
    turned over); otherwise one entry with probability 1."""
    out: dict[tuple[int, ...], float] = {}
    total = sum(w for _, w in worlds)
    for view, w in worlds:
        key = unseen_counts(view)
        out[key] = out.get(key, 0.0) + float(w / total)
    return list(out.items())


def over_shoes(mixture, f: Callable[[tuple[int, ...]], float]) -> float:
    """Average of f(unseen counts) over the possible shoes."""
    return sum(p * f(deck) for deck, p in mixture)


def next_hand_value(rules: BlackjackRules, deck: tuple[int, ...], exact: bool = False) -> float:
    """Expected result of the next hand, per unit bet, dealt from `deck` (cards per
    rank A..T), with optimal play: > 0 means the player has the edge (bet more).

    exact=True: exact for this shoe, but slow: ~1-10 s on one deck, ~20-30 s on six.
    exact=False (~0.2 s): the first three cards (your two, the dealer's up card)
    are dealt exactly from `deck`; the rest of the hand is drawn with the
    proportions of what is left, without further removal. Measured error vs exact:
    <= 0.03% on 6 decks (fresh, 120 or 200 cards dealt), <= 0.15% on a single deck
    with 20 cards dealt (smaller shoes: larger error)."""
    deck = tuple(deck)
    if exact:
        return BlackjackSolver(rules, shoe=deck).round_value()
    payout = float(rules.blackjack_pays)
    solvers: dict = {}
    ev = 0.0
    for c1 in range(10):
        for u in range(10):
            for c2 in range(10):
                rest, p = deck, 1.0
                for c in (c1, u, c2):
                    if not rest[c]:
                        p = 0.0
                        break
                    p *= rest[c] / sum(rest)
                    rest = _remove(rest, c)
                if not p:
                    continue
                k = _bj_rank(u)
                p_dealer_bj = 0.0 if k is None else rest[k] / sum(rest)
                if _total((c1, c2))[0] == 21:
                    ev += p * (1 - p_dealer_bj) * payout
                    continue
                if rest not in solvers:
                    n = sum(rest)
                    solvers[rest] = BlackjackSolver(rules, proportions=tuple(c / n for c in rest))
                value = solvers[rest].initial(RANKS[c1], RANKS[c2], RANKS[u])[1]
                ev += p * (-p_dealer_bj + (1 - p_dealer_bj) * value)
    return ev


# --- playing a policy through the engine (arena) ----------------------------------------

def engine_policy(policy: Policy):
    """Adapt a blackjack policy to the engine's policy signature. It reads only what
    the player sees: its active hand, the up card, the number of hands."""
    def play(view, player, options, rng):
        cards, up, n_hands, split_aces = situation_of(view)
        situation = Situation(cards, up, tuple(o.kind for o in options), n_hands, split_aces)
        return Option(policy(situation))
    return play


def solver_policy(solver: BlackjackSolver) -> Policy:
    """The solver's own choices, decided on the cards of the hand being played and
    the up card. After a split it ignores the cards of the other hands (a small
    simplification: only for playing, never for computing values)."""
    def play(sit: Situation) -> str:
        if len(sit.cards) == 2 and sit.n_hands == 1:
            return solver.initial(sit.cards[0], sit.cards[1], sit.up)[0]
        cards = tuple(sorted(RANKS.index(c) for c in sit.cards))
        u = RANKS.index(sit.up)
        actions = tuple(a for a in sit.options if a != "split")
        return solver._choose(solver._unseen(cards, u), u, cards, sit.n_hands, sit.split_aces, actions)[0]
    return play
