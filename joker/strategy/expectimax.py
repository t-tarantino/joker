"""Exact expected value and best choices for games with ONE deciding player
against chance and fixed procedures (ROADMAP rung 1, strategy.md levels L4/L5).

"Expectimax": at the player's decisions take the best option, at chance steps take
the probability-weighted average. Generic: it only uses the engine (rules), the
observations (what the player sees) and `Game.utility`.

Hidden information is handled exactly. The player never decides in a physical
state, but in an *information state*: the set of worlds consistent with what it
has seen, each with its probability (its belief). Worlds are split into
information states by replaying the player's observations (S7.4), so rule-forced
knowledge, e.g. "the dealer peeked and has no blackjack", is used automatically.
The player's options are the same in every world of an information state (S7.8).

Exact rational arithmetic (Fractions): this is the reference (oracle) that faster,
game-specific methods are checked against.

Caching ("same situation, compute once"):
- copies of the same card type are interchangeable (S1.1): states that differ only
  by which copy is where are merged (`canonical`), and a draw branches once per
  card *type*, with probability = copies / cards in the zone;
- the chance-and-procedure stretch after each state is computed once per state
  (`_expand`), and the value of each information state once per belief (`value`).
Requirement: game variables never hold card ids (true for every game so far).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from ..core import Engine, Option, State, StepKind, View

Belief = dict  # canonical State -> probability (Fraction), summing to 1


class SoloExpectimax:
    def __init__(self, engine: Engine, player: int = 0) -> None:
        self.engine = engine
        self.player = player
        type_index: dict = {}
        self._type = [type_index.setdefault(c.type, len(type_index)) for c in engine.cards]
        self._expanded: dict[State, tuple] = {}
        self._values: dict[frozenset, Fraction] = {}

    # --- public API ----------------------------------------------------------------------

    def root(self, match_state=None) -> tuple[Fraction, list[tuple[Fraction, Belief]]]:
        """From the start of a hand: (probability x utility of the paths that end
        before any decision, [(probability of reaching it, belief), ...] for every
        first information state of the player)."""
        s = self.canonical(self.engine.new_hand(match_state))
        ev, decisions = self._expand(s)
        return ev, self._group(decisions)

    def game_value(self, match_state=None) -> Fraction:
        """Expected utility of the whole hand under optimal play."""
        ev, firsts = self.root(match_state)
        return ev + sum(p * self.value(b) for p, b in firsts)

    def value(self, belief: Belief) -> Fraction:
        """Expected utility of an information state under optimal play from here."""
        key = frozenset(belief.items())
        if key not in self._values:
            self._values[key] = max(self.option_values(belief).values())
        return self._values[key]

    def option_values(self, belief: Belief) -> dict[Option, Fraction]:
        """Expected utility of each option, then optimal play."""
        s = next(iter(belief))
        return {o: self._q(belief, o) for o in self.engine.legal_options(s, self.player)}

    def best_option(self, belief: Belief) -> Option:
        values = self.option_values(belief)
        return max(values, key=values.get)

    def view(self, belief: Belief) -> View:
        """A view of one world of the information state, for reading what the player
        sees (all worlds agree on it)."""
        return self.engine.view(next(iter(belief)))

    # --- canonical states (copy symmetry, S1.1) ---------------------------------------------

    def canonical(self, s: State) -> State:
        """Copy symmetry (S1.1): see Engine.canonical."""
        return self.engine.canonical(s)

    # --- the recursion --------------------------------------------------------------------------

    def _q(self, belief: Belief, opt: Option) -> Fraction:
        ev = Fraction(0)
        decisions: list = []
        for s, w in belief.items():
            s2, event = self.engine.apply(s, {self.player: opt})
            obs = self.engine.observe(event, self.player)
            sub_ev, sub_decisions = self._expand(self.canonical(s2))
            ev += w * sub_ev
            decisions.extend(((obs,) + suffix, d, w * p) for suffix, d, p in sub_decisions)
        return ev + sum(p * self.value(b) for p, b in self._group(decisions))

    @staticmethod
    def _group(decisions) -> list[tuple[Fraction, Belief]]:
        """Split decision worlds into information states by observation history:
        [(probability of the information state, its belief), ...]."""
        groups: dict[tuple, dict] = {}
        for history, s, p in decisions:
            group = groups.setdefault(history, {})
            group[s] = group.get(s, 0) + p
        result = []
        for group in groups.values():
            mass = sum(group.values())
            result.append((mass, {s: p / mass for s, p in group.items()}))
        return result

    def _expand(self, s: State) -> tuple[Fraction, tuple]:
        """Run chance and automatic steps from `s` until the hand ends or the player
        must decide. Returns (sum of probability x utility over the paths that end,
        ((observation history, decision state, probability), ...))."""
        cached = self._expanded.get(s)
        if cached is not None:
            return cached
        engine = self.engine
        step = engine.next_step(s)
        if step.kind is StepKind.END:
            result = (Fraction(engine.game.utility(engine.view(s), self.player)), ())
        elif step.kind is StepKind.CHOICE:
            if step.actors != (self.player,):
                raise NotImplementedError("SoloExpectimax: another player decides here")
            result = (Fraction(0), (((), s, Fraction(1)),))
        else:
            ev = Fraction(0)
            decisions: list = []
            for outcome, p in self._outcomes(s, step):
                s2, event = engine.apply(s, outcome)
                obs = engine.observe(event, self.player)
                sub_ev, sub_decisions = self._expand(self.canonical(s2))
                ev += p * sub_ev
                decisions.extend(((obs,) + suffix, d, p * q) for suffix, d, q in sub_decisions)
            result = (ev, tuple(decisions))
        self._expanded[s] = result
        return result

    def _outcomes(self, s: State, step) -> list[tuple[Any, Fraction]]:
        if step.kind is StepKind.AUTO:
            return [(None, Fraction(1))]
        if s.pending:                                # a draw: one branch per card type
            ids = s.zones[s.pending[0].src]
            by_type: dict[int, list[int]] = {}
            for cid in ids:
                by_type.setdefault(self._type[cid], []).append(cid)
            return [(group[0], Fraction(len(group), len(ids))) for group in by_type.values()]
        return list(step.outcomes)
